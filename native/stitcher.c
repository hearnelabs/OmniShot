/*
 * OmniShot - High Performance Image Stitching Engine
 * Tailored for Wayland / KDE Plasma 6 scrolling capture
 * Includes multi-anchor full-width correlation, periodic repetition rejection,
 * and static margin detection.
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

typedef struct {
    int offset_y;          // Best vertical offset (pixels)
    int offset_x;          // Horizontal drift (usually 0)
    double confidence;     // Match confidence (0.0 to 1.0, 1.0 is exact match)
    double mean_diff;      // Mean absolute difference per pixel channel
    int is_identical;      // 1 if frames are identical (0 movement)
} StitchResult;

// Fast inline RGB pixel difference (Manhattan distance in RGB space)
static inline int pixel_diff(uint32_t c1, uint32_t c2) {
    int r = ((c1 >> 16) & 0xFF) - ((c2 >> 16) & 0xFF);
    int g = ((c1 >> 8) & 0xFF) - ((c2 >> 8) & 0xFF);
    int b = (c1 & 0xFF) - (c2 & 0xFF);
    return abs(r) + abs(g) + abs(b);
}

// Compute variance / edge count of a horizontal strip to ensure it has features
static double compute_strip_variance(const uint32_t* frame, int width, int y_start, int strip_h, int x_start, int x_end) {
    int64_t diff_sum = 0;
    int count = 0;
    for (int y = y_start; y < y_start + strip_h - 1; y += 2) {
        const uint32_t* r1 = &frame[y * width];
        const uint32_t* r2 = &frame[(y + 1) * width];
        for (int x = x_start; x < x_end; x += 4) {
            diff_sum += pixel_diff(r1[x], r2[x]);
            count++;
        }
    }
    return count > 0 ? (double)diff_sum / count : 0.0;
}

/*
 * Automatically detects static header height and static footer height
 * between two frames by scanning rows with zero or near-zero variance.
 */
void omnishot_detect_static_margins(
    const uint32_t* frame_a,
    const uint32_t* frame_b,
    int width,
    int height,
    int margin_x_left,
    int margin_x_right,
    int* out_header_h,
    int* out_footer_h
) {
    if (!frame_a || !frame_b || width <= 0 || height <= 0) {
        if (out_header_h) *out_header_h = 0;
        if (out_footer_h) *out_footer_h = 0;
        return;
    }

    int left = margin_x_left > 0 ? margin_x_left : 10;
    int right = width - (margin_x_right > 0 ? margin_x_right : 24);
    if (right <= left) {
        left = 0;
        right = width;
    }

    // 1. Detect static header from top down
    int header_limit = height / 3;
    int header_h = 0;
    for (int y = 0; y < header_limit; y++) {
        const uint32_t* ra = &frame_a[y * width];
        const uint32_t* rb = &frame_b[y * width];
        int64_t diff = 0;
        int count = 0;
        for (int x = left; x < right; x += 4) {
            diff += pixel_diff(ra[x], rb[x]);
            count++;
        }
        double avg = count > 0 ? (double)diff / count : 0.0;
        if (avg < 1.5) {
            header_h = y + 1;
        } else {
            break;
        }
    }

    // 2. Detect static footer / bottom bar / floating buttons from bottom up
    int footer_limit = height / 3;
    int footer_h = 0;
    for (int y = height - 1; y >= height - footer_limit; y--) {
        const uint32_t* ra = &frame_a[y * width];
        const uint32_t* rb = &frame_b[y * width];
        int64_t diff = 0;
        int count = 0;
        for (int x = left; x < right; x += 4) {
            diff += pixel_diff(ra[x], rb[x]);
            count++;
        }
        double avg = count > 0 ? (double)diff / count : 0.0;
        if (avg < 1.5) {
            footer_h = height - y;
        } else {
            break;
        }
    }

    if (out_header_h) *out_header_h = header_h;
    if (out_footer_h) *out_footer_h = footer_h;
}

/*
 * Checks if two frames are effectively identical in their scrollable body
 */
int check_identical(
    const uint32_t* frame_a,
    const uint32_t* frame_b,
    int width,
    int height,
    int margin_x,
    int margin_y
) {
    int y_start = margin_y + 15;
    int y_end = height - margin_y - 15;
    if (y_start >= y_end) {
        y_start = height / 4;
        y_end = 3 * height / 4;
    }

    int64_t diff_sum = 0;
    int samples = 0;

    int y_step = (y_end - y_start) / 20;
    if (y_step < 1) y_step = 1;

    for (int y = y_start; y < y_end; y += y_step) {
        const uint32_t* row_a = &frame_a[y * width];
        const uint32_t* row_b = &frame_b[y * width];
        for (int x = margin_x; x < width - margin_x; x += 6) {
            diff_sum += pixel_diff(row_a[x], row_b[x]);
            samples++;
        }
    }

    if (samples == 0) return 1;
    double avg = (double)diff_sum / samples;
    return (avg < 1.2) ? 1 : 0;
}

/*
 * Finds the vertical offset d between prev_frame and curr_frame
 *
 * When the user scrolls DOWN, the content moves UP.
 * Therefore, row (y) in curr_frame corresponds to row (y + d) in prev_frame.
 *
 * Uses full-width multi-anchor cross-correlation across multiple distinct vertical
 * bands. This guarantees that repeating lists (like emails, tables, or chat rows)
 * cannot trigger false-positive periodic matches, and eliminates text squashing.
 */
int omnishot_find_vertical_offset(
    const uint32_t* prev_frame,
    const uint32_t* curr_frame,
    int width,
    int height,
    int min_d,
    int max_d,
    int margin_x_left,
    int margin_x_right,
    int margin_y_top,
    int margin_y_bottom,
    double max_allowed_diff,
    StitchResult* out_result
) {
    if (!prev_frame || !curr_frame || width <= 0 || height <= 0) {
        if (out_result) memset(out_result, 0, sizeof(StitchResult));
        return -1;
    }

    int x_start = margin_x_left > 0 ? margin_x_left : 10;
    int x_end = width - (margin_x_right > 0 ? margin_x_right : 24);
    if (x_end <= x_start + 40) {
        x_start = 0;
        x_end = width;
    }

    int y_top = margin_y_top + 10;
    int y_bottom = height - margin_y_bottom - 10;
    int scroll_h = y_bottom - y_top;
    if (scroll_h < 80) {
        y_top = 0;
        y_bottom = height;
        scroll_h = height;
    }

    // 1. Check if frames are identical (0 displacement)
    if (check_identical(prev_frame, curr_frame, width, height, x_start, margin_y_top)) {
        if (out_result) {
            out_result->offset_y = 0;
            out_result->offset_x = 0;
            out_result->confidence = 1.0;
            out_result->mean_diff = 0.0;
            out_result->is_identical = 1;
        }
        return 0;
    }

    if (min_d < 1) min_d = 1;
    if (max_d > (int)(scroll_h * 0.85)) max_d = (int)(scroll_h * 0.85);
    if (max_d < min_d) max_d = min_d;

    // Full-height multi-line template height: 44 to 80px
    int strip_h = (int)(scroll_h * 0.16);
    if (strip_h < 44) strip_h = 44;
    if (strip_h > 80) strip_h = 80;
    if (strip_h >= scroll_h / 2) strip_h = scroll_h / 3;

    // Pick 2 high-variance anchors across the upper half of the scrollable region
    int candidate_ys[4];
    candidate_ys[0] = y_top + (int)(scroll_h * 0.08);
    candidate_ys[1] = y_top + (int)(scroll_h * 0.20);
    candidate_ys[2] = y_top + (int)(scroll_h * 0.32);
    candidate_ys[3] = y_top + (int)(scroll_h * 0.44);

    double variances[4] = {-1.0, -1.0, -1.0, -1.0};
    for (int i = 0; i < 4; i++) {
        int cy = candidate_ys[i];
        if (cy + max_d + strip_h <= y_bottom) {
            variances[i] = compute_strip_variance(curr_frame, width, cy, strip_h, x_start, x_end);
        }
    }

    int idx1 = -1, idx2 = -1;
    double max_v1 = -1.0, max_v2 = -1.0;
    for (int i = 0; i < 4; i++) {
        if (variances[i] > max_v1) {
            max_v2 = max_v1;
            idx2 = idx1;
            max_v1 = variances[i];
            idx1 = i;
        } else if (variances[i] > max_v2) {
            max_v2 = variances[i];
            idx2 = i;
        }
    }

    int anchor1_y = (idx1 >= 0) ? candidate_ys[idx1] : candidate_ys[0];
    int anchor2_y = (idx2 >= 0 && max_v2 > 0.5) ? candidate_ys[idx2] : -1;

    double best_diff = 1e9;
    int best_d = -1;

    for (int d = min_d; d <= max_d; d++) {
        if (anchor1_y + d + strip_h > y_bottom) break;

        int64_t diff1 = 0;
        int count1 = 0;
        for (int sy = 0; sy < strip_h; sy += 2) {
            const uint32_t* r_curr = &curr_frame[(anchor1_y + sy) * width];
            const uint32_t* r_prev = &prev_frame[(anchor1_y + d + sy) * width];
            for (int x = x_start; x < x_end; x += 3) {
                diff1 += pixel_diff(r_curr[x], r_prev[x]);
                count1++;
            }
        }
        double avg1 = count1 > 0 ? (double)diff1 / count1 : 1e9;
        double combined = avg1;

        if (anchor2_y >= 0 && (anchor2_y + d + strip_h <= y_bottom)) {
            int64_t diff2 = 0;
            int count2 = 0;
            for (int sy = 0; sy < strip_h; sy += 2) {
                const uint32_t* r2_curr = &curr_frame[(anchor2_y + sy) * width];
                const uint32_t* r2_prev = &prev_frame[(anchor2_y + d + sy) * width];
                for (int x = x_start; x < x_end; x += 3) {
                    diff2 += pixel_diff(r2_curr[x], r2_prev[x]);
                    count2++;
                }
            }
            double avg2 = count2 > 0 ? (double)diff2 / count2 : 1e9;
            // Both anchors must agree: penalize partial/periodic matches where only one matches
            combined = (avg1 * 0.5) + (avg2 * 0.5) + (fabs(avg1 - avg2) * 0.3);
        }

        if (combined < best_diff) {
            best_diff = combined;
            best_d = d;
            if (best_diff < 0.2) {
                break; // Exact bit-for-bit match found
            }
        }
    }

    if (best_d > 0 && best_diff <= max_allowed_diff) {
        if (out_result) {
            out_result->offset_y = best_d;
            out_result->offset_x = 0;
            out_result->mean_diff = best_diff;
            double conf = 1.0 - (best_diff / max_allowed_diff);
            out_result->confidence = conf > 0.0 ? conf : 0.0;
            out_result->is_identical = 0;
        }
        return best_d;
    }

    if (out_result) {
        out_result->offset_y = -1;
        out_result->offset_x = 0;
        out_result->mean_diff = best_diff;
        out_result->confidence = 0.0;
        out_result->is_identical = 0;
    }
    return -1;
}

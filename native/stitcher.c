/*
 * OmniShot - High Performance Image Stitching Engine
 * Tailored for Wayland / KDE Plasma 6 scrolling capture
 * Includes multi-zone correlation, floating widget rejection, and static margin detection.
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
static double compute_strip_variance(const uint32_t* frame, int width, int y_start, int strip_h, int margin_x_left, int margin_x_right) {
    int64_t diff_sum = 0;
    int count = 0;
    for (int y = y_start; y < y_start + strip_h - 1; y += 2) {
        const uint32_t* r1 = &frame[y * width];
        const uint32_t* r2 = &frame[(y + 1) * width];
        for (int x = margin_x_left; x < width - margin_x_right; x += 4) {
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
            // Check if next 2 rows are also non-static before concluding
            int is_noisy = 0;
            for (int ny = y + 1; ny < y + 3 && ny < header_limit; ny++) {
                const uint32_t* n_ra = &frame_a[ny * width];
                const uint32_t* n_rb = &frame_b[ny * width];
                int64_t n_diff = 0;
                int n_count = 0;
                for (int x = left; x < right; x += 4) {
                    n_diff += pixel_diff(n_ra[x], n_rb[x]);
                    n_count++;
                }
                if (n_count > 0 && ((double)n_diff / n_count) < 1.5) {
                    is_noisy = 1;
                    break;
                }
            }
            if (!is_noisy) {
                break;
            }
        }
    }

    // 2. Detect static footer / bottom bar / floating buttons from bottom up
    int footer_limit = height / 2;
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
            // Check center cluster (floating action button at center-bottom)
            int cx_start = width / 3;
            int cx_end = (2 * width) / 3;
            int64_t c_diff = 0;
            int c_count = 0;
            for (int x = cx_start; x < cx_end; x += 2) {
                c_diff += pixel_diff(ra[x], rb[x]);
                c_count++;
            }
            double c_avg = c_count > 0 ? (double)c_diff / c_count : 0.0;
            if (c_avg < 1.5) {
                // Center cluster is static while sides move -> floating button
                footer_h = height - y;
            } else {
                break;
            }
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
 * Employs horizontal sub-zone correlation (Left, Right) to completely ignore
 * centered or right-aligned floating buttons and scrollbars.
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

    if (min_d < 1) min_d = 1;
    if (max_d >= height - margin_y_bottom - 10) {
        max_d = height - margin_y_bottom - 10;
    }

    int eff_width = width - margin_x_left - margin_x_right;
    if (eff_width <= 20) {
        margin_x_left = 5;
        margin_x_right = 5;
        eff_width = width - 10;
    }

    // Check if frames are identical (0 displacement)
    if (check_identical(prev_frame, curr_frame, width, height, margin_x_left, margin_y_top)) {
        if (out_result) {
            out_result->offset_y = 0;
            out_result->offset_x = 0;
            out_result->confidence = 1.0;
            out_result->mean_diff = 0.0;
            out_result->is_identical = 1;
        }
        return 0;
    }

    int strip_h = 24;
    if (strip_h > (height / 6)) strip_h = (height / 6);
    if (strip_h < 10) strip_h = 10;

    // Pick 3 candidate positions well inside the safe scrollable body
    int candidate_ys[3];
    candidate_ys[0] = margin_y_top + 15;
    candidate_ys[1] = (int)(height * 0.22);
    candidate_ys[2] = (int)(height * 0.40);

    int best_sample_y = candidate_ys[1];
    double max_var = -1.0;

    for (int i = 0; i < 3; i++) {
        int cy = candidate_ys[i];
        if (cy + strip_h < height - margin_y_bottom - 20) {
            double v = compute_strip_variance(curr_frame, width, cy, strip_h, margin_x_left, margin_x_right);
            if (v > max_var) {
                max_var = v;
                best_sample_y = cy;
            }
        }
    }

    int curr_y_start = best_sample_y;

    // Horizontal thirds to isolate floating buttons
    int third_w = eff_width / 3;
    int x_left_start = margin_x_left;
    int x_left_end = x_left_start + third_w;
    int x_right_start = width - margin_x_right - third_w;
    int x_right_end = width - margin_x_right;

    double best_diff = 1e9;
    int best_d = -1;

    for (int d = min_d; d <= max_d; d++) {
        int prev_y_start = curr_y_start + d;
        if (prev_y_start + strip_h >= height - margin_y_bottom) {
            break; // Exceeded bounds
        }

        int64_t diff_left = 0, diff_right = 0;
        int count_left = 0, count_right = 0;

        for (int sy = 0; sy < strip_h; sy++) {
            const uint32_t* r_curr = &curr_frame[(curr_y_start + sy) * width];
            const uint32_t* r_prev = &prev_frame[(prev_y_start + sy) * width];

            // Left third
            for (int x = x_left_start; x < x_left_end; x += 2) {
                diff_left += pixel_diff(r_curr[x], r_prev[x]);
                count_left++;
            }
            // Right third
            for (int x = x_right_start; x < x_right_end; x += 2) {
                diff_right += pixel_diff(r_curr[x], r_prev[x]);
                count_right++;
            }
        }

        double avg_l = count_left > 0 ? (double)diff_left / count_left : 1e9;
        double avg_r = count_right > 0 ? (double)diff_right / count_right : 1e9;

        // Use minimum of left and right to reject floating elements that sit on one side/center
        double avg_zone = fmin(avg_l, avg_r);
        if (avg_l < 10.0 && avg_r < 10.0) {
            avg_zone = (avg_l + avg_r) * 0.5;
        }

        // Secondary confirmation strip to prevent periodic repetition errors
        int strip2_h = 20;
        int curr_y2_start = curr_y_start + strip_h + 24;
        double avg_combined = avg_zone;

        if (curr_y2_start + strip2_h + d < height - margin_y_bottom) {
            int prev_y2_start = curr_y2_start + d;
            int64_t diff2_l = 0;
            int count2_l = 0;
            for (int sy = 0; sy < strip2_h; sy++) {
                const uint32_t* r2_curr = &curr_frame[(curr_y2_start + sy) * width];
                const uint32_t* r2_prev = &prev_frame[(prev_y2_start + sy) * width];
                for (int x = x_left_start; x < x_left_end; x += 2) {
                    diff2_l += pixel_diff(r2_curr[x], r2_prev[x]);
                    count2_l++;
                }
            }
            if (count2_l > 0) {
                double avg2 = (double)diff2_l / count2_l;
                avg_combined = (avg_zone * 0.6) + (avg2 * 0.4);
            }
        }

        if (avg_combined < best_diff) {
            best_diff = avg_combined;
            best_d = d;
            if (best_diff < 0.2) {
                break; // Near-perfect match
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

/*
 * OmniShot - High Performance Image Stitching Engine
 * Tailored for Wayland / KDE Plasma 6 scrolling capture
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifdef __x86_64__
#include <immintrin.h>
#endif

typedef struct {
    int offset_y;          // Best vertical offset (pixels)
    int offset_x;          // Horizontal drift (usually 0)
    double confidence;     // Match confidence (0.0 to 1.0, 1.0 is exact match)
    double mean_diff;      // Mean absolute difference per pixel channel
    int is_identical;      // 1 if frames are identical (0 movement)
} StitchResult;

// Fast inline RGB pixel difference
static inline int pixel_diff(uint32_t c1, uint32_t c2) {
    int r = ((c1 >> 16) & 0xFF) - ((c2 >> 16) & 0xFF);
    int g = ((c1 >> 8) & 0xFF) - ((c2 >> 8) & 0xFF);
    int b = (c1 & 0xFF) - (c2 & 0xFF);
    return abs(r) + abs(g) + abs(b);
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
    int y_start = margin_y + 10;
    int y_end = height - margin_y - 10;
    if (y_start >= y_end) {
        y_start = height / 4;
        y_end = 3 * height / 4;
    }

    int64_t diff_sum = 0;
    int samples = 0;

    int y_step = (y_end - y_start) / 16;
    if (y_step < 1) y_step = 1;

    for (int y = y_start; y < y_end; y += y_step) {
        const uint32_t* row_a = &frame_a[y * width];
        const uint32_t* row_b = &frame_b[y * width];
        for (int x = margin_x; x < width - margin_x; x += 4) {
            diff_sum += pixel_diff(row_a[x], row_b[x]);
            samples++;
        }
    }

    if (samples == 0) return 1;
    double avg = (double)diff_sum / samples;
    return (avg < 1.0) ? 1 : 0;
}

/*
 * Finds the vertical offset d between prev_frame and curr_frame
 *
 * When the user scrolls DOWN, the content moves UP.
 * Therefore, row (y) in curr_frame corresponds to row (y + d) in prev_frame.
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

    // Check if frames are identical
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

    // Define search strip from curr_frame
    // We sample a strip starting right below the top margin
    int strip_h = 48;
    if (strip_h > (height / 5)) strip_h = (height / 5);
    if (strip_h < 12) strip_h = 12;

    int curr_y_start = margin_y_top + 10;

    // Also a second verification strip further down in curr_frame
    int strip2_h = 32;
    int curr_y2_start = curr_y_start + strip_h + 20;
    int use_strip2 = (curr_y2_start + strip2_h < height - margin_y_bottom - 60);

    double best_diff = 1e9;
    int best_d = -1;

    for (int d = min_d; d <= max_d; d++) {
        int prev_y_start = curr_y_start + d;
        if (prev_y_start + strip_h >= height - margin_y_bottom) {
            break; // Exceeded bounds
        }

        int64_t total_diff = 0;
        int count = 0;

        // Primary strip match
        for (int sy = 0; sy < strip_h; sy += 2) {
            const uint32_t* r_curr = &curr_frame[(curr_y_start + sy) * width];
            const uint32_t* r_prev = &prev_frame[(prev_y_start + sy) * width];

            for (int x = margin_x_left; x < width - margin_x_right; x += 4) {
                total_diff += pixel_diff(r_curr[x], r_prev[x]);
                count++;
            }
        }

        if (count == 0) continue;
        double avg1 = (double)total_diff / count;

        // If primary strip is promising, check secondary strip for strong multi-point confirmation
        double avg_combined = avg1;
        if (use_strip2 && avg1 < (best_diff * 1.5 + 5.0)) {
            int prev_y2_start = curr_y2_start + d;
            if (prev_y2_start + strip2_h < height - margin_y_bottom) {
                int64_t total_diff2 = 0;
                int count2 = 0;
                for (int sy = 0; sy < strip2_h; sy += 2) {
                    const uint32_t* r2_curr = &curr_frame[(curr_y2_start + sy) * width];
                    const uint32_t* r2_prev = &prev_frame[(prev_y2_start + sy) * width];
                    for (int x = margin_x_left; x < width - margin_x_right; x += 4) {
                        total_diff2 += pixel_diff(r2_curr[x], r2_prev[x]);
                        count2++;
                    }
                }
                if (count2 > 0) {
                    double avg2 = (double)total_diff2 / count2;
                    avg_combined = (avg1 * 0.6) + (avg2 * 0.4);
                }
            }
        }

        if (avg_combined < best_diff) {
            best_diff = avg_combined;
            best_d = d;
            // Short-circuit if near-perfect match found
            if (best_diff < 0.2) {
                break;
            }
        }
    }

    if (best_d > 0 && best_diff <= max_allowed_diff) {
        if (out_result) {
            out_result->offset_y = best_d;
            out_result->offset_x = 0;
            out_result->mean_diff = best_diff;
            // Confidence calculation: max 1.0 down to 0.0 at max_allowed_diff
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

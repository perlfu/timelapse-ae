
/*
 * gcc -Wall -o avgimg `pkg-config --cflags --libs MagickWand` avgimg.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <assert.h>

#include <wand/MagickWand.h>


#define N_BINS      (16)
#define LOG_N_BINS  (4)   // base 2
#define PX_TO_BIN(p,d)  (((uint32_t) p) >> (d - LOG_N_BINS))
#define BIN_TO_PX(b,d)  (((uint32_t) b) << (d - LOG_N_BINS))
#define PS_RED      (0)
#define PS_GREEN    (1)
#define PS_BLUE     (2)


typedef struct _pixelstat_t {
    uint16_t count;
    double sum[3], gsum[3];
    double min[3], max[3];
    uint16_t hist[3][N_BINS];
} pixelstat_t;


static inline void update_stats(pixelstat_t *p,
        const unsigned int depth,
        const double r, const double g, const double b) {
    p->count++;
    
    p->sum[PS_RED  ]    += r;
    p->sum[PS_GREEN]    += g;
    p->sum[PS_BLUE ]    += b;
    p->gsum[PS_RED  ]   += log10(r);
    p->gsum[PS_GREEN]   += log10(g);
    p->gsum[PS_BLUE ]   += log10(b);

    if (r < p->min[PS_RED])
        p->min[PS_RED  ] = r;
    if (g < p->min[PS_GREEN])
        p->min[PS_GREEN] = g;
    if (b < p->min[PS_BLUE])
        p->min[PS_BLUE ] = b;
    
    if (r > p->max[PS_RED])
        p->max[PS_RED  ] = r;
    if (g > p->max[PS_GREEN])
        p->max[PS_GREEN] = g;
    if (b > p->max[PS_BLUE])
        p->max[PS_BLUE ] = b;
    
    p->hist[PS_RED  ][PX_TO_BIN(r, depth)] += 1;
    p->hist[PS_GREEN][PX_TO_BIN(g, depth)] += 1;
    p->hist[PS_BLUE ][PX_TO_BIN(b, depth)] += 1;
}

static inline void init_stats(pixelstat_t *p) {
    int i, j;

    for (i = 0; i < 3; ++i) {
        p->sum[i] = 0.0;
        p->min[i] = ((double)(1 << 30));
        p->max[i] = 0.0;
        for (j = 0; j < N_BINS; ++j)
            p->hist[i][j] = 0;
    }
}

static void average_stats(pixelstat_t *p) {
    if (p->count > 0) {
        int i;
    
        for (i = 0; i < 3; ++i) {
            p->sum[i] /= (double) p->count;
            p->gsum[i] = __exp10(p->gsum[i] / ((double)p->count));

            /*
            for (j = 0; j < N_BINS; ++j) {
                p->hist[i][j] = (
                    (((double)p->hist[i][j]) * 1000.0) 
                        / ((double) p->count)
                );
            }
            */
        }
    }
}

static void average_stats_with_count(pixelstat_t *p, const double count) {
    int i;

    for (i = 0; i < 3; ++i) {
        p->sum[i] /= count;
        p->gsum[i] = __exp10(p->gsum[i] / count);
    }
}

static void wand_exception(MagickWand *wand) {
    ExceptionType severity;
    char *description = MagickGetException(wand, &severity);
    fprintf(stderr, "%s %s %lu %s\n", GetMagickModule(), description);
    MagickRelinquishMemory(description);
    exit(-1);
}
#define ThrowWandException(w)   wand_exception((w))

static void save_wand(const char *prefix, const char *name, MagickWand *wand)
{
    MagickBooleanType status;
    char *buf;
    
    if (prefix) {
        unsigned int buflen = strlen(prefix) + strlen(name) + 8;
        buf = (char *) malloc(buflen + 8);
        snprintf (buf, buflen, "%s-%s.png", prefix, name);
    } else {
        unsigned int buflen = strlen(name) + 8;
        buf = (char *) malloc(buflen + 8);
        strcpy (buf, name);
    }
    
    fprintf (stdout, "saving %s...\n", buf);
    status = MagickWriteImages(wand, buf, MagickTrue);
    if (status == MagickFalse) {
        ThrowWandException(wand);
    }
    fprintf (stdout, "saved.\n");

    free(buf);
}

static void pixel_avg(MagickPixelPacket *pixel, pixelstat_t *stats) {
    pixel->red   = stats->sum[PS_RED];
    pixel->green = stats->sum[PS_GREEN];
    pixel->blue  = stats->sum[PS_BLUE];
}

static void pixel_geoavg(MagickPixelPacket *pixel, pixelstat_t *stats) {
    pixel->red   = stats->gsum[PS_RED];
    pixel->green = stats->gsum[PS_GREEN];
    pixel->blue  = stats->gsum[PS_BLUE];
}

static void pixel_min(MagickPixelPacket *pixel, pixelstat_t *stats) {
    pixel->red   = stats->min[PS_RED];
    pixel->green = stats->min[PS_GREEN];
    pixel->blue  = stats->min[PS_BLUE];
}

static void pixel_max(MagickPixelPacket *pixel, pixelstat_t *stats) {
    pixel->red   = stats->max[PS_RED];
    pixel->green = stats->max[PS_GREEN];
    pixel->blue  = stats->max[PS_BLUE];
}

static void pixel_diff(MagickPixelPacket *pixel, pixelstat_t *stats) {
    pixel->red   = stats->max[PS_RED]   - stats->min[PS_RED];
    pixel->green = stats->max[PS_GREEN] - stats->min[PS_GREEN];
    pixel->blue  = stats->max[PS_BLUE]  - stats->min[PS_BLUE];
}

static unsigned int selected_bin = 0;
static void pixel_bin(MagickPixelPacket *pixel, pixelstat_t *stats) {
    double base  = (1 << pixel->depth) - 1; //BIN_TO_PX(selected_bin, pixel->depth);
    double count = stats->count;
    pixel->red      = (base * stats->hist[PS_RED  ][selected_bin]) / count;
    pixel->green    = (base * stats->hist[PS_GREEN][selected_bin]) / count;
    pixel->blue     = (base * stats->hist[PS_BLUE ][selected_bin]) / count;
}

static void generate_and_save(const char *prefix, const char *name, MagickWand *wand, pixelstat_t *stats, void (*f)(MagickPixelPacket *, pixelstat_t *)) {
    PixelIterator *iter = NewPixelIterator(wand);
    unsigned int width = MagickGetImageWidth(wand); 
    unsigned int height = MagickGetImageHeight(wand); 
    unsigned int x, y;

    fprintf(stdout, "generate %s...\n", name);
    
    for (y = 0; y < height; ++y) {
        unsigned long row_width;
        pixelstat_t *sr = (stats + (y * width));
        PixelWand **pixels = PixelGetNextIteratorRow(iter, &row_width);
        if (pixels == NULL)
            break;
        for (x = 0; x < row_width; ++x) {
            MagickPixelPacket pixel;
            PixelGetMagickColor(pixels[x], &pixel);
            f(&pixel, sr++);
            PixelSetMagickColor(pixels[x], &pixel);
        }
        PixelSyncIterator(iter);
    }
    DestroyPixelIterator(iter);

    save_wand(prefix, name, wand);
}

static void output_usage(const char *name)
{
    fprintf(stdout, 
        "Usage: %s [OPTION] <output> <input0> [<input1> ...]\n"
        "\n"
        "Where OPTION is one of:\n"
        "  -b  output histographic bins\n"
        "  -g  output only geometric mean image\n"
        "  -m  output only arithmetic mean image\n"
        "\n"
        "Input files can be prefixed with a weight, e.g.\n"
        "    avgimg -g out.png 0.2:in0.png 0.8:in1.png\n"
        "\n",
        name);
}

static void usage(const char *name) {
    output_usage(name);
    exit(1);
}

#define X_TRUE 1
#define X_FALSE 0

int main(int argc, char **argv)
{
    const char *prog_name = argv[0];
    const char *prefix = NULL;
    MagickBooleanType status;
    MagickWand *output_wand;
    pixelstat_t *stats;
    unsigned int width, height, n_pixels;
    unsigned int i, x, y;
    double weight_sum = 0.0;
    int count = 0;
    int output_bins = X_FALSE;
    int output_only_gmean = X_FALSE;
    int output_only_amean = X_FALSE;
    int file_n = 2;

    if (argc < 3) {
        output_usage(argv[0]);
        exit(1);
    }

    for (i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "-b") == 0) {
            output_bins = X_TRUE;
        } else if (strcmp(argv[i], "-g") == 0) {
            output_only_gmean = X_TRUE;
        } else if (strcmp(argv[i], "-m") == 0) {
            output_only_amean = X_TRUE;
        } else if (strcmp(argv[i], "--") == 0) {
            i++;
            break;
        } else if (argv[i][0] == '-') {
            usage(prog_name);
        } else {
            break;
        }
    }
    file_n = i;

    // need to have at least 2 arguments remaining
    if (file_n > (argc - 2)) {
        usage(prog_name);
    } else {
        prefix = argv[file_n++];
    }

    // need to have consistent options
    if ((output_bins + output_only_gmean + output_only_amean) > 1) {
        fprintf (stdout, "inconsistent options\n");
        usage(prog_name);
    }

    MagickWandGenesis();
    
    // setup output and buffers
    output_wand = NewMagickWand();
    status = MagickReadImage(output_wand, argv[file_n]);
    if (status == MagickFalse)
        ThrowWandException(output_wand);

    width   = MagickGetImageWidth(output_wand);
    height  = MagickGetImageHeight(output_wand);
    n_pixels= width * height;
    stats   = (pixelstat_t *) malloc(sizeof(pixelstat_t) * n_pixels);
    for (i = 0; i < n_pixels; ++i) {
        init_stats(&(stats[i]));
    }

    fprintf (stdout, "output: %s (%ux%u)\n", prefix, width, height);

    // read input files
    while (file_n < argc) {
        const char *fn = argv[file_n];
        const char *split = index(fn, ':');
        double weight = 1.0;
        MagickWand *wand = NewMagickWand();

        // look for custom weight at the beginning 
        if (split) {
            char buffer[64];
            int split_p = split - fn;

            assert(split_p < sizeof(buffer));
            strncpy(buffer, fn, split_p);
            buffer[split_p] = '\0';
            weight          = strtold(buffer, NULL);
            fn              = split + 1;
        }

        fprintf (stdout, "read: %s (weight: %.5f)\n", fn, weight);

        status = MagickReadImage(wand, fn);
        if (status == MagickFalse)
            ThrowWandException(wand);

        if ((MagickGetImageHeight(wand) == height) ||
            (MagickGetImageWidth(wand) == width)) {
            pixelstat_t *sp = stats;
            PixelIterator *iter = NewPixelIterator(wand);

            for (y = 0; y < height; ++y) {
                unsigned long row_width;
                PixelWand **pixels = PixelGetNextIteratorRow(iter, &row_width);
                if (pixels == NULL)
                    break;

                for (x = 0; x < row_width; ++x) {
                    MagickPixelPacket pixel;
                    PixelGetMagickColor(pixels[x], &pixel);
                    update_stats(&(sp[x]),
                        pixel.depth,
                        pixel.red * weight,
                        pixel.green * weight,
                        pixel.blue * weight);
                }

                sp += width;
            }

            DestroyPixelIterator(iter);
            weight_sum += weight;
            count += 1;
        } else {
            fprintf(stderr, "! input dimensions for %s (%ux%u) do not match output dimensions %ux%u; ignoring\n",
                fn,
                (unsigned int) MagickGetImageWidth(wand),
                (unsigned int) MagickGetImageHeight(wand),
                width,
                height);
        }

        DestroyMagickWand(wand);

        file_n++;
    } 

    // compute output
    fprintf (stdout, "computing...\n");
    
    if (weight_sum != count) {
        for (i = 0; i < n_pixels; ++i) {
            average_stats_with_count(&(stats[i]), weight_sum);
        }
    } else {
        for (i = 0; i < n_pixels; ++i) {
            average_stats(&(stats[i]));
        }
    }
    
    fprintf (stdout, "computed.\n");

    // write output
    if (output_only_amean) {
        generate_and_save(NULL, prefix, output_wand, stats, pixel_avg);
    } else if (output_only_gmean) {
        generate_and_save(NULL, prefix, output_wand, stats, pixel_geoavg);
    } else {
        generate_and_save(prefix, "avg", output_wand, stats, pixel_avg);
        generate_and_save(prefix, "geoavg", output_wand, stats, pixel_geoavg);
        generate_and_save(prefix, "min", output_wand, stats, pixel_min);
        generate_and_save(prefix, "max", output_wand, stats, pixel_max);
        generate_and_save(prefix, "diff", output_wand, stats, pixel_diff);
        if (output_bins) {
            for (i = 0; i < 16; ++i) {
                char name[8];
                snprintf(name, sizeof(name), "bin%02d", i);
                selected_bin = i;
                generate_and_save(prefix, name, output_wand, stats, pixel_bin);
            }
        }
    }

    free(stats);
    DestroyMagickWand(output_wand);
    MagickWandTerminus();
    
    return 0;
}

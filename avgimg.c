
/*
 * gcc -Wall -o avgimg `pkg-config --cflags --libs MagickWand` avgimg.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

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
    unsigned int buflen = strlen(prefix) + strlen(name) + 8;
    char *buf = (char *) malloc(buflen + 8);
    snprintf (buf, buflen, "%s-%s.png", prefix, name);
    
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
        "Usage: [-b] %s <out> <in0> [<in1> ...]\n", 
        name);
}

int main(int argc, char **argv)
{
    const char *prefix = NULL;
    MagickBooleanType status;
    MagickWand *output_wand;
    pixelstat_t *stats;
    unsigned int width, height, n_pixels;
    unsigned int i, x, y;
    int output_bins = 0;
    int file_n = 2;

    if (argc < 3) {
        output_usage(argv[0]);
        exit(1);
    }

    if (strcmp(argv[1], "-b") == 0) {
        output_bins = 1;
        if (argc < 4) {
            output_usage(argv[0]);
            exit(1);
        }
        prefix = argv[2];
    } else {
        prefix = argv[1];
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
        MagickWand *wand = NewMagickWand();

        fprintf (stdout, "read: %s\n", fn);

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
                    update_stats(&(sp[x]), pixel.depth, pixel.red, pixel.green, pixel.blue);
                }

                sp += width;
            }

            DestroyPixelIterator(iter);
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
    
    for (i = 0; i < n_pixels; ++i) {
        average_stats(&(stats[i]));
    }
    
    fprintf (stdout, "computed.\n");

    // write output
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

    free(stats);
    DestroyMagickWand(output_wand);
    MagickWandTerminus();
    
    return 0;
}

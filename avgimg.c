#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <wand/MagickWand.h>

int main(int argc, char **argv)
{
#define ThrowViewException(view) \
{ \
      description=GetWandViewException(view,&severity); \
      (void) fprintf(stderr,"%s %s %lu %s\n",GetMagickModule(),description); \
      description=(char *) MagickRelinquishMemory(description); \
      exit(-1); \
}
#define ThrowWandException(wand) \
{ \
      description=MagickGetException(wand,&severity); \
      (void) fprintf(stderr,"%s %s %lu %s\n",GetMagickModule(),description); \
      description=(char *) MagickRelinquishMemory(description); \
      exit(-1); \
}

    const char *output = NULL;

    char *description;
    ExceptionType severity;
    MagickBooleanType status;
    MagickWand *output_wand;
    PixelIterator *output_iter;
    double *red, *blue, *green;
    unsigned int width, height, n_pixels;
    unsigned int i, x, y;
    int n_files = 0;
    int file_n = 2;

    if (argc < 3)
    {
        fprintf(stdout, 
            "Usage: %s <out> <in0> [<in1> ...]\n", 
            argv[0]);
        exit(1);
    }

    output = argv[1];

    MagickWandGenesis();
    
    // setup output and buffers
    output_wand = NewMagickWand();
    status = MagickReadImage(output_wand, argv[file_n]);
    if (status == MagickFalse)
        ThrowWandException(output_wand);

    width   = MagickGetImageWidth(output_wand);
    height  = MagickGetImageHeight(output_wand);
    n_pixels= width * height;
    red     = (double *) malloc(sizeof(double) * n_pixels);
    green   = (double *) malloc(sizeof(double) * n_pixels);
    blue    = (double *) malloc(sizeof(double) * n_pixels);
    for (i = 0; i < n_pixels; ++i) {
        red[i] = 0.0;
        green[i] = 0.0;
        blue[i] = 0.0;
    }

    fprintf (stdout, "output: %s (%ux%u)\n", output, width, height);

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
            double *rp = red;
            double *gp = green;
            double *bp = blue;

            PixelIterator *iter = NewPixelIterator(wand);

            for (y = 0; y < height; ++y) {
                unsigned long row_width;
                PixelWand **pixels = PixelGetNextIteratorRow(iter, &row_width);
                if (pixels == NULL)
                    break;

                for (x = 0; x < row_width; ++x) {
                    MagickPixelPacket pixel;
                    PixelGetMagickColor(pixels[x], &pixel);

                    rp[x] += (double) pixel.red;
                    gp[x] += (double) pixel.green;
                    bp[x] += (double) pixel.blue;
                }
                rp += width;
                gp += width;
                bp += width;
            }

            DestroyPixelIterator(iter);
            n_files++;
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
        red[i] /= (double) n_files;
        green[i] /= (double) n_files;
        blue[i] /= (double) n_files;
    }

    output_iter = NewPixelIterator(output_wand);
    for (y = 0; y < height; ++y) {
        unsigned long row_width;
        double *rr = (red + (y * width));
        double *gr = (green + (y * width));
        double *br = (blue + (y * width));
        PixelWand **pixels = PixelGetNextIteratorRow(output_iter, &row_width);
        if (pixels == NULL)
            break;
        for (x = 0; x < row_width; ++x) {
            MagickPixelPacket pixel;
            PixelGetMagickColor(pixels[x], &pixel);
            pixel.red   = *(rr++);
            pixel.green = *(gr++);
            pixel.blue  = *(br++);
            PixelSetMagickColor(pixels[x], &pixel);
        }
        PixelSyncIterator(output_iter);
    }
    
    free (red);
    free (blue);
    free (green);
    
    fprintf (stdout, "computed.\n");

    // write output
    fprintf (stdout, "saving...\n");
    status = MagickWriteImages(output_wand, output, MagickTrue);
    if (status == MagickFalse)
        ThrowWandException(output_wand);
    fprintf (stdout, "saved.\n");
    
    DestroyMagickWand(output_wand);
    MagickWandTerminus();
    
    return 0;
}

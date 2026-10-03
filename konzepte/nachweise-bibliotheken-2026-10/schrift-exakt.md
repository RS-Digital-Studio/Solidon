# Schriftzüge gegen die exakte Glyphenfläche (RM-471)

Sollwert: die Summe der Glyphenflächen aus den Kurven der Schriftdatei, gelesen mit fontTools und exakt integriert (`AreaPen`), skaliert auf die Schriftgröße. Comfortaa und Dancing Script fehlen, weil sich ihre Striche überdecken und die Summe der Glyphenflächen die Deckung doppelt zählte. Fehler in Prozent der exakten Fläche, alt mit matplotlib, neu mit HarfBuzz. Gemessen am 03.10.2026 unter Windows.

| Schrift | Schnitt | Text | Höhe mm | exakt mm² | Fehler alt % | Fehler neu % | Punkte alt | Punkte neu |
|---|---|---|---:|---:|---:|---:|---:|---:|
| DejaVu Sans | regular | SOLIDON3D | 3 | 12.882 | -1.318 | -0.005 | 246 | 841 |
| DejaVu Sans | regular | SOLIDON3D | 10 | 143.134 | -0.439 | -0.005 | 270 | 841 |
| DejaVu Sans | regular | SOLIDON3D | 50 | 3578.362 | -0.240 | -0.005 | 414 | 841 |
| DejaVu Sans | regular | Deckel 120 x 80 | 3 | 14.585 | -1.333 | -0.003 | 350 | 1054 |
| DejaVu Sans | regular | Deckel 120 x 80 | 10 | 162.061 | -1.005 | -0.003 | 362 | 1054 |
| DejaVu Sans | regular | Deckel 120 x 80 | 50 | 4051.513 | -0.161 | -0.003 | 532 | 1054 |
| DejaVu Sans | regular | Ölwanne Größe 12,5 mm | 3 | 22.001 | -0.880 | -0.001 | 592 | 1481 |
| DejaVu Sans | regular | Ölwanne Größe 12,5 mm | 10 | 244.457 | -0.631 | -0.001 | 604 | 1481 |
| DejaVu Sans | regular | Ölwanne Größe 12,5 mm | 50 | 6111.430 | -0.126 | -0.001 | 839 | 1481 |
| DejaVu Sans | regular | AVATAR Toyota WAVE | 3 | 21.282 | -0.371 | +0.000 | 310 | 619 |
| DejaVu Sans | regular | AVATAR Toyota WAVE | 10 | 236.466 | -0.371 | +0.000 | 310 | 619 |
| DejaVu Sans | regular | AVATAR Toyota WAVE | 50 | 5911.640 | -0.028 | +0.000 | 403 | 619 |
| DejaVu Sans | regular | Mama illu &%8 | 3 | 14.104 | -0.648 | -0.002 | 408 | 929 |
| DejaVu Sans | regular | Mama illu &%8 | 10 | 156.709 | -0.648 | -0.002 | 408 | 929 |
| DejaVu Sans | regular | Mama illu &%8 | 50 | 3917.727 | -0.314 | -0.002 | 549 | 929 |
| DejaVu Sans | bold | SOLIDON3D | 3 | 22.095 | -0.875 | -0.008 | 262 | 801 |
| DejaVu Sans | bold | SOLIDON3D | 10 | 245.497 | -0.516 | -0.008 | 278 | 801 |
| DejaVu Sans | bold | SOLIDON3D | 50 | 6137.430 | -0.077 | -0.008 | 389 | 801 |
| DejaVu Sans | bold | Deckel 120 x 80 | 3 | 24.754 | -1.149 | -0.008 | 352 | 994 |
| DejaVu Sans | bold | Deckel 120 x 80 | 10 | 275.044 | -1.020 | -0.008 | 360 | 994 |
| DejaVu Sans | bold | Deckel 120 x 80 | 50 | 6876.108 | -0.170 | -0.008 | 537 | 994 |
| DejaVu Sans | bold | Ölwanne Größe 12,5 mm | 3 | 37.825 | -0.913 | -0.004 | 605 | 1410 |
| DejaVu Sans | bold | Ölwanne Größe 12,5 mm | 10 | 420.276 | -0.752 | -0.004 | 617 | 1410 |
| DejaVu Sans | bold | Ölwanne Größe 12,5 mm | 50 | 10506.893 | -0.162 | -0.004 | 844 | 1410 |
| DejaVu Sans | bold | AVATAR Toyota WAVE | 3 | 37.116 | -0.373 | -0.003 | 310 | 601 |
| DejaVu Sans | bold | AVATAR Toyota WAVE | 10 | 412.397 | -0.373 | -0.003 | 310 | 601 |
| DejaVu Sans | bold | AVATAR Toyota WAVE | 50 | 10309.915 | -0.064 | -0.003 | 410 | 601 |
| DejaVu Sans | bold | Mama illu &%8 | 3 | 23.810 | -0.702 | -0.000 | 420 | 894 |
| DejaVu Sans | bold | Mama illu &%8 | 10 | 264.553 | -0.702 | -0.000 | 420 | 894 |
| DejaVu Sans | bold | Mama illu &%8 | 50 | 6613.837 | -0.344 | -0.000 | 564 | 894 |
| DejaVu Sans | italic | SOLIDON3D | 3 | 12.814 | -0.439 | -0.006 | 290 | 815 |
| DejaVu Sans | italic | SOLIDON3D | 10 | 142.373 | -0.524 | -0.006 | 296 | 815 |
| DejaVu Sans | italic | SOLIDON3D | 50 | 3559.332 | -0.024 | -0.006 | 422 | 815 |
| DejaVu Sans | italic | Deckel 120 x 80 | 3 | 14.521 | -0.596 | -0.008 | 418 | 986 |
| DejaVu Sans | italic | Deckel 120 x 80 | 10 | 161.345 | -0.634 | -0.008 | 421 | 986 |
| DejaVu Sans | italic | Deckel 120 x 80 | 50 | 4033.635 | -0.347 | -0.008 | 562 | 986 |
| DejaVu Sans | italic | Ölwanne Größe 12,5 mm | 3 | 21.913 | -0.406 | -0.004 | 712 | 1446 |
| DejaVu Sans | italic | Ölwanne Größe 12,5 mm | 10 | 243.482 | -0.406 | -0.004 | 712 | 1446 |
| DejaVu Sans | italic | Ölwanne Größe 12,5 mm | 50 | 6087.052 | -0.163 | -0.004 | 906 | 1446 |
| DejaVu Sans | italic | AVATAR Toyota WAVE | 3 | 21.153 | -0.131 | -0.002 | 350 | 636 |
| DejaVu Sans | italic | AVATAR Toyota WAVE | 10 | 235.033 | -0.131 | -0.002 | 350 | 636 |
| DejaVu Sans | italic | AVATAR Toyota WAVE | 50 | 5875.818 | -0.086 | -0.002 | 419 | 636 |
| DejaVu Sans | italic | Mama illu &%8 | 3 | 14.121 | -0.564 | -0.004 | 448 | 916 |
| DejaVu Sans | italic | Mama illu &%8 | 10 | 156.897 | -0.564 | -0.004 | 448 | 916 |
| DejaVu Sans | italic | Mama illu &%8 | 50 | 3922.420 | -0.300 | -0.004 | 588 | 916 |
| DejaVu Sans | bold_italic | SOLIDON3D | 3 | 22.153 | -0.465 | -0.012 | 286 | 781 |
| DejaVu Sans | bold_italic | SOLIDON3D | 10 | 246.148 | -0.378 | -0.012 | 292 | 781 |
| DejaVu Sans | bold_italic | SOLIDON3D | 50 | 6153.712 | -0.148 | -0.012 | 417 | 781 |
| DejaVu Sans | bold_italic | Deckel 120 x 80 | 3 | 24.784 | -0.666 | -0.010 | 436 | 972 |
| DejaVu Sans | bold_italic | Deckel 120 x 80 | 10 | 275.378 | -0.666 | -0.010 | 436 | 972 |
| DejaVu Sans | bold_italic | Deckel 120 x 80 | 50 | 6884.461 | -0.329 | -0.010 | 585 | 972 |
| DejaVu Sans | bold_italic | Ölwanne Größe 12,5 mm | 3 | 37.778 | -0.487 | -0.012 | 697 | 1425 |
| DejaVu Sans | bold_italic | Ölwanne Größe 12,5 mm | 10 | 419.757 | -0.440 | -0.012 | 702 | 1425 |
| DejaVu Sans | bold_italic | Ölwanne Größe 12,5 mm | 50 | 10493.928 | -0.219 | -0.012 | 896 | 1425 |
| DejaVu Sans | bold_italic | AVATAR Toyota WAVE | 3 | 36.779 | -0.187 | -0.007 | 342 | 614 |
| DejaVu Sans | bold_italic | AVATAR Toyota WAVE | 10 | 408.654 | -0.187 | -0.007 | 342 | 614 |
| DejaVu Sans | bold_italic | AVATAR Toyota WAVE | 50 | 10216.348 | -0.088 | -0.007 | 419 | 614 |
| DejaVu Sans | bold_italic | Mama illu &%8 | 3 | 23.876 | -0.644 | -0.016 | 443 | 893 |
| DejaVu Sans | bold_italic | Mama illu &%8 | 10 | 265.289 | -0.644 | -0.016 | 443 | 893 |
| DejaVu Sans | bold_italic | Mama illu &%8 | 50 | 6632.227 | -0.329 | -0.016 | 578 | 893 |
| DejaVu Serif | regular | SOLIDON3D | 3 | 12.418 | -0.173 | -0.002 | 308 | 896 |
| DejaVu Serif | regular | SOLIDON3D | 10 | 137.979 | +0.306 | -0.002 | 320 | 896 |
| DejaVu Serif | regular | SOLIDON3D | 50 | 3449.464 | -0.124 | -0.002 | 474 | 896 |
| DejaVu Serif | regular | Deckel 120 x 80 | 3 | 13.682 | -1.374 | -0.024 | 389 | 1110 |
| DejaVu Serif | regular | Deckel 120 x 80 | 10 | 152.023 | -0.997 | -0.024 | 402 | 1110 |
| DejaVu Serif | regular | Deckel 120 x 80 | 50 | 3800.568 | -0.189 | -0.024 | 592 | 1110 |
| DejaVu Serif | regular | Ölwanne Größe 12,5 mm | 3 | 20.931 | -0.632 | -0.018 | 733 | 1653 |
| DejaVu Serif | regular | Ölwanne Größe 12,5 mm | 10 | 232.572 | -0.474 | -0.018 | 740 | 1653 |
| DejaVu Serif | regular | Ölwanne Größe 12,5 mm | 50 | 5814.296 | -0.143 | -0.018 | 996 | 1653 |
| DejaVu Serif | regular | AVATAR Toyota WAVE | 3 | 20.414 | -0.349 | +0.001 | 426 | 730 |
| DejaVu Serif | regular | AVATAR Toyota WAVE | 10 | 226.818 | -0.349 | +0.001 | 426 | 730 |
| DejaVu Serif | regular | AVATAR Toyota WAVE | 50 | 5670.462 | -0.039 | +0.001 | 518 | 730 |
| DejaVu Serif | regular | Mama illu &%8 | 3 | 14.083 | -0.599 | -0.001 | 483 | 1000 |
| DejaVu Serif | regular | Mama illu &%8 | 10 | 156.475 | -0.599 | -0.001 | 483 | 1000 |
| DejaVu Serif | regular | Mama illu &%8 | 50 | 3911.885 | -0.331 | -0.001 | 626 | 1000 |
| DejaVu Serif | bold | SOLIDON3D | 3 | 20.005 | -1.120 | +0.000 | 284 | 904 |
| DejaVu Serif | bold | SOLIDON3D | 10 | 222.283 | -0.497 | +0.000 | 308 | 904 |
| DejaVu Serif | bold | SOLIDON3D | 50 | 5557.077 | -0.137 | +0.000 | 455 | 904 |
| DejaVu Serif | bold | Deckel 120 x 80 | 3 | 22.241 | -1.314 | -0.018 | 391 | 1162 |
| DejaVu Serif | bold | Deckel 120 x 80 | 10 | 247.117 | -1.077 | -0.018 | 403 | 1162 |
| DejaVu Serif | bold | Deckel 120 x 80 | 50 | 6177.925 | -0.190 | -0.018 | 600 | 1162 |
| DejaVu Serif | bold | Ölwanne Größe 12,5 mm | 3 | 33.803 | -0.903 | -0.023 | 724 | 1685 |
| DejaVu Serif | bold | Ölwanne Größe 12,5 mm | 10 | 375.588 | -0.717 | -0.023 | 736 | 1685 |
| DejaVu Serif | bold | Ölwanne Größe 12,5 mm | 50 | 9389.699 | -0.195 | -0.023 | 1032 | 1685 |
| DejaVu Serif | bold | AVATAR Toyota WAVE | 3 | 30.814 | -0.382 | -0.002 | 426 | 755 |
| DejaVu Serif | bold | AVATAR Toyota WAVE | 10 | 342.378 | -0.382 | -0.002 | 426 | 755 |
| DejaVu Serif | bold | AVATAR Toyota WAVE | 50 | 8559.454 | -0.062 | -0.002 | 531 | 755 |
| DejaVu Serif | bold | Mama illu &%8 | 3 | 22.337 | -0.662 | -0.029 | 483 | 1025 |
| DejaVu Serif | bold | Mama illu &%8 | 10 | 248.185 | -0.662 | -0.029 | 483 | 1025 |
| DejaVu Serif | bold | Mama illu &%8 | 50 | 6204.625 | -0.336 | -0.029 | 633 | 1025 |
| DejaVu Serif | italic | SOLIDON3D | 3 | 12.420 | -0.142 | -0.003 | 308 | 894 |
| DejaVu Serif | italic | SOLIDON3D | 10 | 137.999 | +0.195 | -0.003 | 326 | 894 |
| DejaVu Serif | italic | SOLIDON3D | 50 | 3449.981 | -0.118 | -0.003 | 472 | 894 |
| DejaVu Serif | italic | Deckel 120 x 80 | 3 | 13.259 | -1.518 | -0.016 | 383 | 1155 |
| DejaVu Serif | italic | Deckel 120 x 80 | 10 | 147.321 | -1.075 | -0.016 | 402 | 1155 |
| DejaVu Serif | italic | Deckel 120 x 80 | 50 | 3683.025 | -0.309 | -0.016 | 590 | 1155 |
| DejaVu Serif | italic | Ölwanne Größe 12,5 mm | 3 | 20.252 | -0.730 | -0.026 | 727 | 1725 |
| DejaVu Serif | italic | Ölwanne Größe 12,5 mm | 10 | 225.023 | -0.533 | -0.026 | 745 | 1725 |
| DejaVu Serif | italic | Ölwanne Größe 12,5 mm | 50 | 5625.581 | -0.234 | -0.026 | 984 | 1725 |
| DejaVu Serif | italic | AVATAR Toyota WAVE | 3 | 20.474 | -0.360 | -0.002 | 428 | 766 |
| DejaVu Serif | italic | AVATAR Toyota WAVE | 10 | 227.491 | -0.337 | -0.002 | 431 | 766 |
| DejaVu Serif | italic | AVATAR Toyota WAVE | 50 | 5687.278 | -0.103 | -0.002 | 506 | 766 |
| DejaVu Serif | italic | Mama illu &%8 | 3 | 13.570 | -0.599 | -0.013 | 454 | 956 |
| DejaVu Serif | italic | Mama illu &%8 | 10 | 150.777 | -0.528 | -0.013 | 460 | 956 |
| DejaVu Serif | italic | Mama illu &%8 | 50 | 3769.424 | -0.256 | -0.013 | 593 | 956 |
| DejaVu Serif | bold_italic | SOLIDON3D | 3 | 20.005 | -1.115 | +0.003 | 284 | 917 |
| DejaVu Serif | bold_italic | SOLIDON3D | 10 | 222.273 | -0.533 | +0.003 | 312 | 917 |
| DejaVu Serif | bold_italic | SOLIDON3D | 50 | 5556.828 | -0.133 | +0.003 | 451 | 917 |
| DejaVu Serif | bold_italic | Deckel 120 x 80 | 3 | 21.779 | -1.413 | -0.017 | 386 | 1196 |
| DejaVu Serif | bold_italic | Deckel 120 x 80 | 10 | 241.983 | -1.033 | -0.017 | 408 | 1196 |
| DejaVu Serif | bold_italic | Deckel 120 x 80 | 50 | 6049.587 | -0.260 | -0.017 | 593 | 1196 |
| DejaVu Serif | bold_italic | Ölwanne Größe 12,5 mm | 3 | 33.288 | -0.981 | -0.026 | 715 | 1756 |
| DejaVu Serif | bold_italic | Ölwanne Größe 12,5 mm | 10 | 369.867 | -0.756 | -0.026 | 737 | 1756 |
| DejaVu Serif | bold_italic | Ölwanne Größe 12,5 mm | 50 | 9246.679 | -0.233 | -0.026 | 1019 | 1756 |
| DejaVu Serif | bold_italic | AVATAR Toyota WAVE | 3 | 30.998 | -0.412 | -0.004 | 428 | 788 |
| DejaVu Serif | bold_italic | AVATAR Toyota WAVE | 10 | 344.425 | -0.378 | -0.004 | 430 | 788 |
| DejaVu Serif | bold_italic | AVATAR Toyota WAVE | 50 | 8610.620 | -0.088 | -0.004 | 522 | 788 |
| DejaVu Serif | bold_italic | Mama illu &%8 | 3 | 21.882 | -0.719 | -0.034 | 449 | 991 |
| DejaVu Serif | bold_italic | Mama illu &%8 | 10 | 243.130 | -0.676 | -0.034 | 451 | 991 |
| DejaVu Serif | bold_italic | Mama illu &%8 | 50 | 6078.251 | -0.319 | -0.034 | 588 | 991 |
| DejaVu Sans Mono | regular | SOLIDON3D | 3 | 12.280 | -1.177 | -0.008 | 254 | 803 |
| DejaVu Sans Mono | regular | SOLIDON3D | 10 | 136.444 | -0.694 | -0.008 | 270 | 803 |
| DejaVu Sans Mono | regular | SOLIDON3D | 50 | 3411.094 | -0.104 | -0.008 | 384 | 803 |
| DejaVu Sans Mono | regular | Deckel 120 x 80 | 3 | 14.492 | -1.358 | -0.039 | 399 | 1108 |
| DejaVu Sans Mono | regular | Deckel 120 x 80 | 10 | 161.021 | -1.070 | -0.039 | 411 | 1108 |
| DejaVu Sans Mono | regular | Deckel 120 x 80 | 50 | 4025.517 | -0.264 | -0.039 | 592 | 1108 |
| DejaVu Sans Mono | regular | Ölwanne Größe 12,5 mm | 3 | 20.578 | -0.883 | -0.009 | 611 | 1469 |
| DejaVu Sans Mono | regular | Ölwanne Größe 12,5 mm | 10 | 228.647 | -0.782 | -0.009 | 617 | 1469 |
| DejaVu Sans Mono | regular | Ölwanne Größe 12,5 mm | 50 | 5716.169 | -0.146 | -0.009 | 822 | 1469 |
| DejaVu Sans Mono | regular | AVATAR Toyota WAVE | 3 | 19.961 | -0.372 | -0.001 | 318 | 637 |
| DejaVu Sans Mono | regular | AVATAR Toyota WAVE | 10 | 221.794 | -0.372 | -0.001 | 318 | 637 |
| DejaVu Sans Mono | regular | AVATAR Toyota WAVE | 50 | 5544.838 | -0.056 | -0.001 | 410 | 637 |
| DejaVu Sans Mono | regular | Mama illu &%8 | 3 | 13.213 | -0.549 | -0.008 | 464 | 925 |
| DejaVu Sans Mono | regular | Mama illu &%8 | 10 | 146.812 | -0.549 | -0.008 | 464 | 925 |
| DejaVu Sans Mono | regular | Mama illu &%8 | 50 | 3670.305 | -0.355 | -0.008 | 595 | 925 |
| DejaVu Sans Mono | bold | SOLIDON3D | 3 | 17.070 | -1.226 | -0.008 | 254 | 746 |
| DejaVu Sans Mono | bold | SOLIDON3D | 10 | 189.663 | -0.865 | -0.008 | 270 | 746 |
| DejaVu Sans Mono | bold | SOLIDON3D | 50 | 4741.572 | -0.212 | -0.008 | 374 | 746 |
| DejaVu Sans Mono | bold | Deckel 120 x 80 | 3 | 20.458 | -1.310 | -0.021 | 396 | 1044 |
| DejaVu Sans Mono | bold | Deckel 120 x 80 | 10 | 227.312 | -1.100 | -0.021 | 408 | 1044 |
| DejaVu Sans Mono | bold | Deckel 120 x 80 | 50 | 5682.802 | -0.297 | -0.021 | 564 | 1044 |
| DejaVu Sans Mono | bold | Ölwanne Größe 12,5 mm | 3 | 29.340 | -0.948 | -0.016 | 608 | 1367 |
| DejaVu Sans Mono | bold | Ölwanne Größe 12,5 mm | 10 | 326.004 | -0.875 | -0.016 | 614 | 1367 |
| DejaVu Sans Mono | bold | Ölwanne Größe 12,5 mm | 50 | 8150.091 | -0.250 | -0.016 | 815 | 1367 |
| DejaVu Sans Mono | bold | AVATAR Toyota WAVE | 3 | 27.990 | -0.400 | -0.005 | 310 | 586 |
| DejaVu Sans Mono | bold | AVATAR Toyota WAVE | 10 | 311.001 | -0.400 | -0.005 | 310 | 586 |
| DejaVu Sans Mono | bold | AVATAR Toyota WAVE | 50 | 7775.014 | -0.096 | -0.005 | 402 | 586 |
| DejaVu Sans Mono | bold | Mama illu &%8 | 3 | 18.561 | -0.748 | -0.025 | 447 | 861 |
| DejaVu Sans Mono | bold | Mama illu &%8 | 10 | 206.230 | -0.748 | -0.025 | 447 | 861 |
| DejaVu Sans Mono | bold | Mama illu &%8 | 50 | 5155.748 | -0.431 | -0.025 | 581 | 861 |
| DejaVu Sans Mono | italic | SOLIDON3D | 3 | 12.261 | -0.627 | -0.003 | 318 | 778 |
| DejaVu Sans Mono | italic | SOLIDON3D | 10 | 136.230 | -0.627 | -0.003 | 318 | 778 |
| DejaVu Sans Mono | italic | SOLIDON3D | 50 | 3405.752 | -0.227 | -0.003 | 418 | 778 |
| DejaVu Sans Mono | italic | Deckel 120 x 80 | 3 | 14.627 | -0.639 | -0.028 | 480 | 1087 |
| DejaVu Sans Mono | italic | Deckel 120 x 80 | 10 | 162.526 | -0.689 | -0.028 | 481 | 1087 |
| DejaVu Sans Mono | italic | Deckel 120 x 80 | 50 | 4063.151 | -0.417 | -0.028 | 636 | 1087 |
| DejaVu Sans Mono | italic | Ölwanne Größe 12,5 mm | 3 | 20.545 | -0.259 | -0.009 | 751 | 1451 |
| DejaVu Sans Mono | italic | Ölwanne Größe 12,5 mm | 10 | 228.275 | -0.294 | -0.009 | 752 | 1451 |
| DejaVu Sans Mono | italic | Ölwanne Größe 12,5 mm | 50 | 5706.866 | -0.203 | -0.009 | 920 | 1451 |
| DejaVu Sans Mono | italic | AVATAR Toyota WAVE | 3 | 19.927 | -0.096 | -0.006 | 350 | 631 |
| DejaVu Sans Mono | italic | AVATAR Toyota WAVE | 10 | 221.408 | -0.096 | -0.006 | 350 | 631 |
| DejaVu Sans Mono | italic | AVATAR Toyota WAVE | 50 | 5535.201 | -0.090 | -0.006 | 421 | 631 |
| DejaVu Sans Mono | italic | Mama illu &%8 | 3 | 13.209 | -0.634 | -0.010 | 506 | 915 |
| DejaVu Sans Mono | italic | Mama illu &%8 | 10 | 146.767 | -0.634 | -0.010 | 506 | 915 |
| DejaVu Sans Mono | italic | Mama illu &%8 | 50 | 3669.186 | -0.350 | -0.010 | 641 | 915 |
| DejaVu Sans Mono | bold_italic | SOLIDON3D | 3 | 17.035 | -0.704 | -0.011 | 325 | 735 |
| DejaVu Sans Mono | bold_italic | SOLIDON3D | 10 | 189.279 | -0.704 | -0.011 | 325 | 735 |
| DejaVu Sans Mono | bold_italic | SOLIDON3D | 50 | 4731.967 | -0.300 | -0.011 | 416 | 735 |
| DejaVu Sans Mono | bold_italic | Deckel 120 x 80 | 3 | 20.377 | -0.840 | -0.026 | 472 | 1018 |
| DejaVu Sans Mono | bold_italic | Deckel 120 x 80 | 10 | 226.414 | -0.765 | -0.026 | 475 | 1018 |
| DejaVu Sans Mono | bold_italic | Deckel 120 x 80 | 50 | 5660.341 | -0.397 | -0.026 | 605 | 1018 |
| DejaVu Sans Mono | bold_italic | Ölwanne Größe 12,5 mm | 3 | 29.272 | -0.682 | -0.021 | 720 | 1350 |
| DejaVu Sans Mono | bold_italic | Ölwanne Größe 12,5 mm | 10 | 325.243 | -0.621 | -0.021 | 724 | 1350 |
| DejaVu Sans Mono | bold_italic | Ölwanne Größe 12,5 mm | 50 | 8131.083 | -0.289 | -0.021 | 888 | 1350 |
| DejaVu Sans Mono | bold_italic | AVATAR Toyota WAVE | 3 | 27.917 | -0.377 | -0.008 | 325 | 588 |
| DejaVu Sans Mono | bold_italic | AVATAR Toyota WAVE | 10 | 310.185 | -0.326 | -0.008 | 329 | 588 |
| DejaVu Sans Mono | bold_italic | AVATAR Toyota WAVE | 50 | 7754.631 | -0.108 | -0.008 | 405 | 588 |
| DejaVu Sans Mono | bold_italic | Mama illu &%8 | 3 | 18.487 | -0.678 | -0.032 | 488 | 858 |
| DejaVu Sans Mono | bold_italic | Mama illu &%8 | 10 | 205.406 | -0.678 | -0.032 | 488 | 858 |
| DejaVu Sans Mono | bold_italic | Mama illu &%8 | 50 | 5135.162 | -0.373 | -0.032 | 619 | 858 |
| Liberation Sans | regular | SOLIDON3D | 3 | 11.602 | -0.732 | -0.009 | 283 | 829 |
| Liberation Sans | regular | SOLIDON3D | 10 | 128.909 | -0.371 | -0.009 | 293 | 829 |
| Liberation Sans | regular | SOLIDON3D | 50 | 3222.718 | -0.409 | -0.009 | 429 | 829 |
| Liberation Sans | regular | Deckel 120 x 80 | 3 | 12.880 | -1.687 | -0.014 | 353 | 1025 |
| Liberation Sans | regular | Deckel 120 x 80 | 10 | 143.113 | -1.417 | -0.014 | 367 | 1025 |
| Liberation Sans | regular | Deckel 120 x 80 | 50 | 3577.835 | -0.260 | -0.014 | 534 | 1025 |
| Liberation Sans | regular | Ölwanne Größe 12,5 mm | 3 | 19.760 | -1.245 | +0.002 | 664 | 1587 |
| Liberation Sans | regular | Ölwanne Größe 12,5 mm | 10 | 219.555 | -1.079 | +0.002 | 672 | 1587 |
| Liberation Sans | regular | Ölwanne Größe 12,5 mm | 50 | 5488.870 | -0.366 | +0.002 | 911 | 1587 |
| Liberation Sans | regular | AVATAR Toyota WAVE | 3 | 19.050 | -0.722 | -0.006 | 367 | 818 |
| Liberation Sans | regular | AVATAR Toyota WAVE | 10 | 211.662 | -0.678 | -0.006 | 370 | 818 |
| Liberation Sans | regular | AVATAR Toyota WAVE | 50 | 5291.561 | -0.153 | -0.006 | 455 | 818 |
| Liberation Sans | regular | Mama illu &%8 | 3 | 12.836 | -0.965 | -0.012 | 477 | 1061 |
| Liberation Sans | regular | Mama illu &%8 | 10 | 142.621 | -0.899 | -0.012 | 483 | 1061 |
| Liberation Sans | regular | Mama illu &%8 | 50 | 3565.527 | -0.520 | -0.012 | 640 | 1061 |
| Liberation Sans | bold | SOLIDON3D | 3 | 16.789 | -0.918 | -0.017 | 265 | 799 |
| Liberation Sans | bold | SOLIDON3D | 10 | 186.545 | -0.566 | -0.017 | 284 | 799 |
| Liberation Sans | bold | SOLIDON3D | 50 | 4663.620 | -0.156 | -0.017 | 395 | 799 |
| Liberation Sans | bold | Deckel 120 x 80 | 3 | 18.414 | -1.480 | -0.023 | 359 | 980 |
| Liberation Sans | bold | Deckel 120 x 80 | 10 | 204.600 | -1.215 | -0.023 | 375 | 980 |
| Liberation Sans | bold | Deckel 120 x 80 | 50 | 5115.011 | -0.393 | -0.023 | 541 | 980 |
| Liberation Sans | bold | Ölwanne Größe 12,5 mm | 3 | 28.598 | -1.006 | -0.018 | 642 | 1503 |
| Liberation Sans | bold | Ölwanne Größe 12,5 mm | 10 | 317.759 | -0.846 | -0.018 | 667 | 1503 |
| Liberation Sans | bold | Ölwanne Größe 12,5 mm | 50 | 7943.969 | -0.275 | -0.018 | 893 | 1503 |
| Liberation Sans | bold | AVATAR Toyota WAVE | 3 | 27.502 | -0.250 | -0.009 | 366 | 795 |
| Liberation Sans | bold | AVATAR Toyota WAVE | 10 | 305.573 | -0.343 | -0.009 | 372 | 795 |
| Liberation Sans | bold | AVATAR Toyota WAVE | 50 | 7639.335 | -0.126 | -0.009 | 459 | 795 |
| Liberation Sans | bold | Mama illu &%8 | 3 | 18.378 | -0.732 | -0.034 | 471 | 1018 |
| Liberation Sans | bold | Mama illu &%8 | 10 | 204.198 | -0.772 | -0.034 | 480 | 1018 |
| Liberation Sans | bold | Mama illu &%8 | 50 | 5104.961 | -0.502 | -0.034 | 631 | 1018 |
| Liberation Sans | italic | SOLIDON3D | 3 | 11.406 | -0.844 | -0.015 | 283 | 836 |
| Liberation Sans | italic | SOLIDON3D | 10 | 126.732 | -0.835 | -0.015 | 286 | 836 |
| Liberation Sans | italic | SOLIDON3D | 50 | 3168.309 | -0.157 | -0.015 | 419 | 836 |
| Liberation Sans | italic | Deckel 120 x 80 | 3 | 12.832 | -0.883 | -0.020 | 398 | 1012 |
| Liberation Sans | italic | Deckel 120 x 80 | 10 | 142.579 | -0.856 | -0.020 | 402 | 1012 |
| Liberation Sans | italic | Deckel 120 x 80 | 50 | 3564.466 | -0.473 | -0.020 | 552 | 1012 |
| Liberation Sans | italic | Ölwanne Größe 12,5 mm | 3 | 19.654 | -0.709 | -0.006 | 708 | 1606 |
| Liberation Sans | italic | Ölwanne Größe 12,5 mm | 10 | 218.374 | -0.712 | -0.006 | 712 | 1606 |
| Liberation Sans | italic | Ölwanne Größe 12,5 mm | 50 | 5459.353 | -0.313 | -0.006 | 927 | 1606 |
| Liberation Sans | italic | AVATAR Toyota WAVE | 3 | 18.942 | -0.207 | -0.008 | 394 | 867 |
| Liberation Sans | italic | AVATAR Toyota WAVE | 10 | 210.466 | -0.257 | -0.008 | 396 | 867 |
| Liberation Sans | italic | AVATAR Toyota WAVE | 50 | 5261.662 | -0.184 | -0.008 | 465 | 867 |
| Liberation Sans | italic | Mama illu &%8 | 3 | 12.808 | -0.603 | -0.015 | 517 | 1099 |
| Liberation Sans | italic | Mama illu &%8 | 10 | 142.306 | -0.644 | -0.015 | 520 | 1099 |
| Liberation Sans | italic | Mama illu &%8 | 50 | 3557.644 | -0.395 | -0.015 | 668 | 1099 |
| Liberation Sans | bold_italic | SOLIDON3D | 3 | 16.515 | -0.880 | -0.016 | 280 | 784 |
| Liberation Sans | bold_italic | SOLIDON3D | 10 | 183.503 | -0.837 | -0.016 | 286 | 784 |
| Liberation Sans | bold_italic | SOLIDON3D | 50 | 4587.564 | -0.337 | -0.016 | 411 | 784 |
| Liberation Sans | bold_italic | Deckel 120 x 80 | 3 | 18.454 | -1.368 | -0.019 | 375 | 981 |
| Liberation Sans | bold_italic | Deckel 120 x 80 | 10 | 205.040 | -1.256 | -0.019 | 387 | 981 |
| Liberation Sans | bold_italic | Deckel 120 x 80 | 50 | 5126.011 | -0.548 | -0.019 | 531 | 981 |
| Liberation Sans | bold_italic | Ölwanne Größe 12,5 mm | 3 | 28.676 | -0.571 | -0.017 | 703 | 1485 |
| Liberation Sans | bold_italic | Ölwanne Größe 12,5 mm | 10 | 318.626 | -0.601 | -0.017 | 706 | 1485 |
| Liberation Sans | bold_italic | Ölwanne Größe 12,5 mm | 50 | 7965.654 | -0.357 | -0.017 | 911 | 1485 |
| Liberation Sans | bold_italic | AVATAR Toyota WAVE | 3 | 27.535 | -0.204 | -0.011 | 390 | 837 |
| Liberation Sans | bold_italic | AVATAR Toyota WAVE | 10 | 305.949 | -0.255 | -0.011 | 394 | 837 |
| Liberation Sans | bold_italic | AVATAR Toyota WAVE | 50 | 7648.716 | -0.192 | -0.011 | 463 | 837 |
| Liberation Sans | bold_italic | Mama illu &%8 | 3 | 18.247 | -0.868 | -0.027 | 512 | 1059 |
| Liberation Sans | bold_italic | Mama illu &%8 | 10 | 202.745 | -0.733 | -0.027 | 516 | 1059 |
| Liberation Sans | bold_italic | Mama illu &%8 | 50 | 5068.615 | -0.403 | -0.027 | 665 | 1059 |
| Liberation Serif | regular | SOLIDON3D | 3 | 9.802 | -1.916 | -0.005 | 298 | 856 |
| Liberation Serif | regular | SOLIDON3D | 10 | 108.910 | -0.339 | -0.005 | 323 | 856 |
| Liberation Serif | regular | SOLIDON3D | 50 | 2722.745 | -0.149 | -0.005 | 453 | 856 |
| Liberation Serif | regular | Deckel 120 x 80 | 3 | 10.086 | -2.410 | -0.018 | 382 | 1020 |
| Liberation Serif | regular | Deckel 120 x 80 | 10 | 112.072 | -1.461 | -0.018 | 397 | 1020 |
| Liberation Serif | regular | Deckel 120 x 80 | 50 | 2801.789 | -0.444 | -0.018 | 531 | 1020 |
| Liberation Serif | regular | Ölwanne Größe 12,5 mm | 3 | 15.242 | -1.710 | -0.065 | 711 | 1445 |
| Liberation Serif | regular | Ölwanne Größe 12,5 mm | 10 | 169.350 | -0.988 | -0.065 | 734 | 1445 |
| Liberation Serif | regular | Ölwanne Größe 12,5 mm | 50 | 4233.762 | -0.488 | -0.065 | 907 | 1445 |
| Liberation Serif | regular | AVATAR Toyota WAVE | 3 | 15.422 | -0.721 | -0.009 | 421 | 725 |
| Liberation Serif | regular | AVATAR Toyota WAVE | 10 | 171.359 | -0.513 | -0.009 | 425 | 725 |
| Liberation Serif | regular | AVATAR Toyota WAVE | 50 | 4283.974 | -0.159 | -0.009 | 485 | 725 |
| Liberation Serif | regular | Mama illu &%8 | 3 | 10.873 | -1.389 | -0.036 | 456 | 915 |
| Liberation Serif | regular | Mama illu &%8 | 10 | 120.811 | -0.985 | -0.036 | 469 | 915 |
| Liberation Serif | regular | Mama illu &%8 | 50 | 3020.286 | -0.431 | -0.036 | 593 | 915 |
| Liberation Serif | bold | SOLIDON3D | 3 | 14.162 | -2.028 | -0.003 | 284 | 831 |
| Liberation Serif | bold | SOLIDON3D | 10 | 157.357 | -0.774 | -0.003 | 312 | 831 |
| Liberation Serif | bold | SOLIDON3D | 50 | 3933.919 | -0.104 | -0.003 | 427 | 831 |
| Liberation Serif | bold | Deckel 120 x 80 | 3 | 14.857 | -1.697 | -0.036 | 401 | 988 |
| Liberation Serif | bold | Deckel 120 x 80 | 10 | 165.081 | -1.241 | -0.036 | 412 | 988 |
| Liberation Serif | bold | Deckel 120 x 80 | 50 | 4127.014 | -0.476 | -0.036 | 536 | 988 |
| Liberation Serif | bold | Ölwanne Größe 12,5 mm | 3 | 23.011 | -1.381 | -0.043 | 702 | 1459 |
| Liberation Serif | bold | Ölwanne Größe 12,5 mm | 10 | 255.674 | -0.919 | -0.043 | 721 | 1459 |
| Liberation Serif | bold | Ölwanne Größe 12,5 mm | 50 | 6391.846 | -0.404 | -0.043 | 874 | 1459 |
| Liberation Serif | bold | AVATAR Toyota WAVE | 3 | 22.410 | -0.441 | -0.010 | 421 | 723 |
| Liberation Serif | bold | AVATAR Toyota WAVE | 10 | 248.998 | -0.373 | -0.010 | 425 | 723 |
| Liberation Serif | bold | AVATAR Toyota WAVE | 50 | 6224.955 | -0.159 | -0.010 | 485 | 723 |
| Liberation Serif | bold | Mama illu &%8 | 3 | 16.008 | -1.434 | -0.038 | 447 | 879 |
| Liberation Serif | bold | Mama illu &%8 | 10 | 177.868 | -1.026 | -0.038 | 459 | 879 |
| Liberation Serif | bold | Mama illu &%8 | 50 | 4446.696 | -0.418 | -0.038 | 578 | 879 |
| Liberation Serif | italic | SOLIDON3D | 3 | 9.569 | +0.151 | -0.009 | 326 | 798 |
| Liberation Serif | italic | SOLIDON3D | 10 | 106.323 | +0.094 | -0.009 | 331 | 798 |
| Liberation Serif | italic | SOLIDON3D | 50 | 2658.067 | -0.188 | -0.009 | 432 | 798 |
| Liberation Serif | italic | Deckel 120 x 80 | 3 | 9.783 | -1.510 | -0.022 | 414 | 1041 |
| Liberation Serif | italic | Deckel 120 x 80 | 10 | 108.696 | -1.094 | -0.022 | 429 | 1041 |
| Liberation Serif | italic | Deckel 120 x 80 | 50 | 2717.396 | -0.528 | -0.022 | 568 | 1041 |
| Liberation Serif | italic | Ölwanne Größe 12,5 mm | 3 | 14.818 | -0.688 | -0.071 | 751 | 1518 |
| Liberation Serif | italic | Ölwanne Größe 12,5 mm | 10 | 164.648 | -0.702 | -0.071 | 754 | 1518 |
| Liberation Serif | italic | Ölwanne Größe 12,5 mm | 50 | 4116.188 | -0.375 | -0.071 | 925 | 1518 |
| Liberation Serif | italic | AVATAR Toyota WAVE | 3 | 15.132 | -0.219 | -0.020 | 430 | 717 |
| Liberation Serif | italic | AVATAR Toyota WAVE | 10 | 168.138 | -0.200 | -0.020 | 432 | 717 |
| Liberation Serif | italic | AVATAR Toyota WAVE | 50 | 4203.455 | -0.114 | -0.020 | 500 | 717 |
| Liberation Serif | italic | Mama illu &%8 | 3 | 10.795 | -1.476 | -0.031 | 458 | 935 |
| Liberation Serif | italic | Mama illu &%8 | 10 | 119.950 | -1.023 | -0.031 | 470 | 935 |
| Liberation Serif | italic | Mama illu &%8 | 50 | 2998.745 | -0.373 | -0.031 | 589 | 935 |
| Liberation Serif | bold_italic | SOLIDON3D | 3 | 13.290 | -0.054 | -0.008 | 318 | 774 |
| Liberation Serif | bold_italic | SOLIDON3D | 10 | 147.664 | -0.275 | -0.008 | 325 | 774 |
| Liberation Serif | bold_italic | SOLIDON3D | 50 | 3691.595 | -0.231 | -0.008 | 429 | 774 |
| Liberation Serif | bold_italic | Deckel 120 x 80 | 3 | 13.761 | -1.092 | -0.029 | 415 | 993 |
| Liberation Serif | bold_italic | Deckel 120 x 80 | 10 | 152.901 | -0.896 | -0.029 | 429 | 993 |
| Liberation Serif | bold_italic | Deckel 120 x 80 | 50 | 3822.533 | -0.431 | -0.029 | 558 | 993 |
| Liberation Serif | bold_italic | Ölwanne Größe 12,5 mm | 3 | 21.580 | -0.578 | -0.054 | 724 | 1440 |
| Liberation Serif | bold_italic | Ölwanne Größe 12,5 mm | 10 | 239.783 | -0.601 | -0.054 | 730 | 1440 |
| Liberation Serif | bold_italic | Ölwanne Größe 12,5 mm | 50 | 5994.583 | -0.325 | -0.054 | 912 | 1440 |
| Liberation Serif | bold_italic | AVATAR Toyota WAVE | 3 | 20.806 | -0.184 | -0.015 | 450 | 694 |
| Liberation Serif | bold_italic | AVATAR Toyota WAVE | 10 | 231.174 | -0.204 | -0.015 | 452 | 694 |
| Liberation Serif | bold_italic | AVATAR Toyota WAVE | 50 | 5779.349 | -0.120 | -0.015 | 512 | 694 |
| Liberation Serif | bold_italic | Mama illu &%8 | 3 | 15.143 | -1.071 | -0.040 | 443 | 876 |
| Liberation Serif | bold_italic | Mama illu &%8 | 10 | 168.253 | -0.806 | -0.040 | 451 | 876 |
| Liberation Serif | bold_italic | Mama illu &%8 | 50 | 4206.329 | -0.337 | -0.040 | 578 | 876 |
| Liberation Mono | regular | SOLIDON3D | 3 | 10.886 | -0.519 | -0.020 | 265 | 795 |
| Liberation Mono | regular | SOLIDON3D | 10 | 120.953 | -0.492 | -0.020 | 286 | 795 |
| Liberation Mono | regular | SOLIDON3D | 50 | 3023.818 | -0.126 | -0.020 | 404 | 795 |
| Liberation Mono | regular | Deckel 120 x 80 | 3 | 13.057 | -1.076 | -0.018 | 381 | 1057 |
| Liberation Mono | regular | Deckel 120 x 80 | 10 | 145.081 | -0.934 | -0.018 | 395 | 1057 |
| Liberation Mono | regular | Deckel 120 x 80 | 50 | 3627.015 | -0.176 | -0.018 | 575 | 1057 |
| Liberation Mono | regular | Ölwanne Größe 12,5 mm | 3 | 19.185 | -0.794 | -0.016 | 647 | 1541 |
| Liberation Mono | regular | Ölwanne Größe 12,5 mm | 10 | 213.170 | -0.807 | -0.016 | 665 | 1541 |
| Liberation Mono | regular | Ölwanne Größe 12,5 mm | 50 | 5329.255 | -0.251 | -0.016 | 890 | 1541 |
| Liberation Mono | regular | AVATAR Toyota WAVE | 3 | 17.697 | -0.612 | -0.003 | 354 | 753 |
| Liberation Mono | regular | AVATAR Toyota WAVE | 10 | 196.629 | -0.536 | -0.003 | 357 | 753 |
| Liberation Mono | regular | AVATAR Toyota WAVE | 50 | 4915.735 | -0.135 | -0.003 | 444 | 753 |
| Liberation Mono | regular | Mama illu &%8 | 3 | 12.411 | -1.519 | -0.015 | 499 | 1030 |
| Liberation Mono | regular | Mama illu &%8 | 10 | 137.901 | -1.136 | -0.015 | 508 | 1030 |
| Liberation Mono | regular | Mama illu &%8 | 50 | 3447.525 | -0.509 | -0.015 | 665 | 1030 |
| Liberation Mono | bold | SOLIDON3D | 3 | 15.618 | -0.556 | -0.021 | 251 | 765 |
| Liberation Mono | bold | SOLIDON3D | 10 | 173.529 | -0.612 | -0.021 | 273 | 765 |
| Liberation Mono | bold | SOLIDON3D | 50 | 4338.223 | -0.228 | -0.021 | 392 | 765 |
| Liberation Mono | bold | Deckel 120 x 80 | 3 | 18.458 | -1.051 | -0.020 | 389 | 1002 |
| Liberation Mono | bold | Deckel 120 x 80 | 10 | 205.087 | -1.031 | -0.020 | 407 | 1002 |
| Liberation Mono | bold | Deckel 120 x 80 | 50 | 5127.165 | -0.366 | -0.020 | 581 | 1002 |
| Liberation Mono | bold | Ölwanne Größe 12,5 mm | 3 | 26.817 | -1.236 | -0.022 | 662 | 1509 |
| Liberation Mono | bold | Ölwanne Größe 12,5 mm | 10 | 297.966 | -1.060 | -0.022 | 673 | 1509 |
| Liberation Mono | bold | Ölwanne Größe 12,5 mm | 50 | 7449.146 | -0.320 | -0.022 | 897 | 1509 |
| Liberation Mono | bold | AVATAR Toyota WAVE | 3 | 25.190 | -0.616 | -0.008 | 376 | 805 |
| Liberation Mono | bold | AVATAR Toyota WAVE | 10 | 279.892 | -0.595 | -0.008 | 378 | 805 |
| Liberation Mono | bold | AVATAR Toyota WAVE | 50 | 6997.302 | -0.147 | -0.008 | 458 | 805 |
| Liberation Mono | bold | Mama illu &%8 | 3 | 16.864 | -1.022 | -0.035 | 486 | 996 |
| Liberation Mono | bold | Mama illu &%8 | 10 | 187.380 | -0.882 | -0.035 | 495 | 996 |
| Liberation Mono | bold | Mama illu &%8 | 50 | 4684.509 | -0.481 | -0.035 | 639 | 996 |
| Liberation Mono | italic | SOLIDON3D | 3 | 10.882 | -0.623 | -0.013 | 318 | 785 |
| Liberation Mono | italic | SOLIDON3D | 10 | 120.910 | -0.771 | -0.013 | 325 | 785 |
| Liberation Mono | italic | SOLIDON3D | 50 | 3022.756 | -0.300 | -0.013 | 435 | 785 |
| Liberation Mono | italic | Deckel 120 x 80 | 3 | 13.038 | -0.852 | -0.019 | 459 | 1059 |
| Liberation Mono | italic | Deckel 120 x 80 | 10 | 144.871 | -0.807 | -0.019 | 465 | 1059 |
| Liberation Mono | italic | Deckel 120 x 80 | 50 | 3621.763 | -0.369 | -0.019 | 621 | 1059 |
| Liberation Mono | italic | Ölwanne Größe 12,5 mm | 3 | 19.164 | -0.830 | -0.019 | 760 | 1559 |
| Liberation Mono | italic | Ölwanne Größe 12,5 mm | 10 | 212.928 | -0.724 | -0.019 | 775 | 1559 |
| Liberation Mono | italic | Ölwanne Größe 12,5 mm | 50 | 5323.201 | -0.386 | -0.019 | 973 | 1559 |
| Liberation Mono | italic | AVATAR Toyota WAVE | 3 | 17.690 | -0.405 | -0.008 | 397 | 828 |
| Liberation Mono | italic | AVATAR Toyota WAVE | 10 | 196.557 | -0.372 | -0.008 | 402 | 828 |
| Liberation Mono | italic | AVATAR Toyota WAVE | 50 | 4913.937 | -0.208 | -0.008 | 477 | 828 |
| Liberation Mono | italic | Mama illu &%8 | 3 | 12.374 | -1.274 | -0.035 | 579 | 1055 |
| Liberation Mono | italic | Mama illu &%8 | 10 | 137.489 | -0.939 | -0.035 | 589 | 1055 |
| Liberation Mono | italic | Mama illu &%8 | 50 | 3437.218 | -0.408 | -0.035 | 727 | 1055 |
| Liberation Mono | bold_italic | SOLIDON3D | 3 | 15.595 | -0.308 | -0.022 | 299 | 758 |
| Liberation Mono | bold_italic | SOLIDON3D | 10 | 173.278 | -0.553 | -0.022 | 308 | 758 |
| Liberation Mono | bold_italic | SOLIDON3D | 50 | 4331.954 | -0.299 | -0.022 | 414 | 758 |
| Liberation Mono | bold_italic | Deckel 120 x 80 | 3 | 18.474 | -0.853 | -0.024 | 441 | 1005 |
| Liberation Mono | bold_italic | Deckel 120 x 80 | 10 | 205.269 | -0.822 | -0.024 | 447 | 1005 |
| Liberation Mono | bold_italic | Deckel 120 x 80 | 50 | 5131.722 | -0.422 | -0.024 | 596 | 1005 |
| Liberation Mono | bold_italic | Ölwanne Größe 12,5 mm | 3 | 26.835 | -0.863 | -0.025 | 731 | 1496 |
| Liberation Mono | bold_italic | Ölwanne Größe 12,5 mm | 10 | 298.161 | -0.761 | -0.025 | 745 | 1496 |
| Liberation Mono | bold_italic | Ölwanne Größe 12,5 mm | 50 | 7454.035 | -0.383 | -0.025 | 937 | 1496 |
| Liberation Mono | bold_italic | AVATAR Toyota WAVE | 3 | 25.188 | -0.567 | -0.009 | 403 | 807 |
| Liberation Mono | bold_italic | AVATAR Toyota WAVE | 10 | 279.872 | -0.438 | -0.009 | 410 | 807 |
| Liberation Mono | bold_italic | AVATAR Toyota WAVE | 50 | 6996.790 | -0.170 | -0.009 | 476 | 807 |
| Liberation Mono | bold_italic | Mama illu &%8 | 3 | 16.909 | -1.123 | -0.042 | 557 | 1014 |
| Liberation Mono | bold_italic | Mama illu &%8 | 10 | 187.881 | -0.807 | -0.042 | 570 | 1014 |
| Liberation Mono | bold_italic | Mama illu &%8 | 50 | 4697.034 | -0.348 | -0.042 | 694 | 1014 |

Größter Flächenfehler je Schrifthöhe: 3 mm alt 2,41 %, neu 0,07 %; 10 mm alt 1,46 %, neu 0,07 %; 50 mm alt 0,55 %, neu 0,07 %. Punkte über alle Zeilen: alt 53 595 (3 mm), 54 608 (10 mm), 71 623 (50 mm), neu 121 356 bei jeder Höhe.

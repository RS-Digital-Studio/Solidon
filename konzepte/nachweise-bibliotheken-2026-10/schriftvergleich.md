# Schriftzüge alt gegen neu (RM-471)

Je Zeile ein Schriftzug, gefüllt über `label_ops.outlines`: alt mit matplotlib (`TextPath`, `to_polygons`) am Stand `f797ec59e`, neu mit HarfBuzz, dem Sehnenfehler aus `glyphs.sag_for` und der Sehnenlänge aus `glyphs.chord_for`. Hausdorff zwischen den Rändern beider Füllungen; die Punkte zählen alle Ringe. Gemessen am 03.10.2026 unter Windows.

| Schrift | Schnitt | Text | Höhe mm | Fläche alt mm² | Fläche neu mm² | Δ Fläche % | Hausdorff mm | Punkte alt | Punkte neu |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| DejaVu Sans | regular | SOLIDON3D | 3 | 12.712 | 12.881 | +1.330 | 0.0251 | 246 | 841 |
| DejaVu Sans | regular | SOLIDON3D | 10 | 142.506 | 143.127 | +0.436 | 0.0753 | 270 | 841 |
| DejaVu Sans | regular | SOLIDON3D | 50 | 3569.762 | 3578.173 | +0.236 | 0.2265 | 414 | 841 |
| DejaVu Sans | regular | Deckel 120 x 80 | 3 | 14.391 | 14.585 | +1.348 | 0.0258 | 350 | 1054 |
| DejaVu Sans | regular | Deckel 120 x 80 | 10 | 160.431 | 162.056 | +1.013 | 0.0780 | 362 | 1054 |
| DejaVu Sans | regular | Deckel 120 x 80 | 50 | 4045.000 | 4051.402 | +0.158 | 0.2293 | 532 | 1054 |
| DejaVu Sans | regular | Ölwanne Größe 12,5 mm | 3 | 21.807 | 22.001 | +0.887 | 0.0232 | 592 | 1481 |
| DejaVu Sans | regular | Ölwanne Größe 12,5 mm | 10 | 242.915 | 244.455 | +0.634 | 0.0746 | 604 | 1481 |
| DejaVu Sans | regular | Ölwanne Größe 12,5 mm | 50 | 6103.753 | 6111.382 | +0.125 | 0.2290 | 839 | 1481 |
| DejaVu Sans | regular | AVATAR Toyota WAVE | 3 | 21.203 | 21.282 | +0.373 | 0.0176 | 310 | 619 |
| DejaVu Sans | regular | AVATAR Toyota WAVE | 10 | 235.589 | 236.466 | +0.373 | 0.0587 | 310 | 619 |
| DejaVu Sans | regular | AVATAR Toyota WAVE | 50 | 5909.995 | 5911.656 | +0.028 | 0.2148 | 403 | 619 |
| DejaVu Sans | regular | Mama illu &%8 | 3 | 14.012 | 14.104 | +0.650 | 0.0159 | 408 | 929 |
| DejaVu Sans | regular | Mama illu &%8 | 10 | 155.694 | 156.706 | +0.650 | 0.0531 | 408 | 929 |
| DejaVu Sans | regular | Mama illu &%8 | 50 | 3905.440 | 3917.646 | +0.313 | 0.2366 | 549 | 929 |
| DejaVu Sans | bold | SOLIDON3D | 3 | 21.901 | 22.093 | +0.875 | 0.0238 | 262 | 801 |
| DejaVu Sans | bold | SOLIDON3D | 10 | 244.232 | 245.478 | +0.510 | 0.0757 | 278 | 801 |
| DejaVu Sans | bold | SOLIDON3D | 50 | 6132.701 | 6136.951 | +0.069 | 0.2361 | 389 | 801 |
| DejaVu Sans | bold | Deckel 120 x 80 | 3 | 24.470 | 24.752 | +1.154 | 0.0216 | 352 | 994 |
| DejaVu Sans | bold | Deckel 120 x 80 | 10 | 272.238 | 275.021 | +1.022 | 0.0735 | 360 | 994 |
| DejaVu Sans | bold | Deckel 120 x 80 | 50 | 6864.435 | 6875.524 | +0.162 | 0.2333 | 537 | 994 |
| DejaVu Sans | bold | Ölwanne Größe 12,5 mm | 3 | 37.479 | 37.823 | +0.917 | 0.0251 | 605 | 1410 |
| DejaVu Sans | bold | Ölwanne Größe 12,5 mm | 10 | 417.115 | 420.259 | +0.754 | 0.0820 | 617 | 1410 |
| DejaVu Sans | bold | Ölwanne Größe 12,5 mm | 50 | 10489.832 | 10506.470 | +0.159 | 0.2465 | 844 | 1410 |
| DejaVu Sans | bold | AVATAR Toyota WAVE | 3 | 36.977 | 37.115 | +0.371 | 0.0188 | 310 | 601 |
| DejaVu Sans | bold | AVATAR Toyota WAVE | 10 | 410.858 | 412.384 | +0.371 | 0.0626 | 310 | 601 |
| DejaVu Sans | bold | AVATAR Toyota WAVE | 50 | 10303.366 | 10309.596 | +0.060 | 0.1992 | 410 | 601 |
| DejaVu Sans | bold | Mama illu &%8 | 3 | 23.643 | 23.810 | +0.707 | 0.0175 | 420 | 894 |
| DejaVu Sans | bold | Mama illu &%8 | 10 | 262.695 | 264.553 | +0.707 | 0.0584 | 420 | 894 |
| DejaVu Sans | bold | Mama illu &%8 | 50 | 6591.081 | 6613.821 | +0.345 | 0.2242 | 564 | 894 |
| DejaVu Sans | italic | SOLIDON3D | 3 | 12.757 | 12.813 | +0.434 | 0.0221 | 290 | 815 |
| DejaVu Sans | italic | SOLIDON3D | 10 | 141.628 | 142.364 | +0.520 | 0.0712 | 296 | 815 |
| DejaVu Sans | italic | SOLIDON3D | 50 | 3558.484 | 3559.108 | +0.018 | 0.2128 | 422 | 815 |
| DejaVu Sans | italic | Deckel 120 x 80 | 3 | 14.434 | 14.520 | +0.592 | 0.0226 | 418 | 986 |
| DejaVu Sans | italic | Deckel 120 x 80 | 10 | 160.323 | 161.332 | +0.629 | 0.0722 | 421 | 986 |
| DejaVu Sans | italic | Deckel 120 x 80 | 50 | 4019.626 | 4033.293 | +0.340 | 0.2305 | 562 | 986 |
| DejaVu Sans | italic | Ölwanne Größe 12,5 mm | 3 | 21.824 | 21.913 | +0.404 | 0.0181 | 712 | 1446 |
| DejaVu Sans | italic | Ölwanne Größe 12,5 mm | 10 | 242.493 | 243.473 | +0.404 | 0.0603 | 712 | 1446 |
| DejaVu Sans | italic | Ölwanne Größe 12,5 mm | 50 | 6077.142 | 6086.836 | +0.160 | 0.2331 | 906 | 1446 |
| DejaVu Sans | italic | AVATAR Toyota WAVE | 3 | 21.125 | 21.152 | +0.129 | 0.0156 | 350 | 636 |
| DejaVu Sans | italic | AVATAR Toyota WAVE | 10 | 234.724 | 235.027 | +0.129 | 0.0519 | 350 | 636 |
| DejaVu Sans | italic | AVATAR Toyota WAVE | 50 | 5870.749 | 5875.671 | +0.084 | 0.2178 | 419 | 636 |
| DejaVu Sans | italic | Mama illu &%8 | 3 | 14.041 | 14.120 | +0.563 | 0.0159 | 448 | 916 |
| DejaVu Sans | italic | Mama illu &%8 | 10 | 156.012 | 156.891 | +0.563 | 0.0529 | 448 | 916 |
| DejaVu Sans | italic | Mama illu &%8 | 50 | 3910.672 | 3922.277 | +0.297 | 0.2271 | 588 | 916 |
| DejaVu Sans | bold_italic | SOLIDON3D | 3 | 22.050 | 22.151 | +0.455 | 0.0192 | 286 | 781 |
| DejaVu Sans | bold_italic | SOLIDON3D | 10 | 245.219 | 246.120 | +0.367 | 0.0636 | 292 | 781 |
| DejaVu Sans | bold_italic | SOLIDON3D | 50 | 6144.598 | 6152.995 | +0.137 | 0.2314 | 417 | 781 |
| DejaVu Sans | bold_italic | Deckel 120 x 80 | 3 | 24.619 | 24.782 | +0.661 | 0.0179 | 436 | 972 |
| DejaVu Sans | bold_italic | Deckel 120 x 80 | 10 | 273.543 | 275.351 | +0.661 | 0.0597 | 436 | 972 |
| DejaVu Sans | bold_italic | Deckel 120 x 80 | 50 | 6861.822 | 6883.784 | +0.320 | 0.2467 | 585 | 972 |
| DejaVu Sans | bold_italic | Ölwanne Größe 12,5 mm | 3 | 37.594 | 37.774 | +0.477 | 0.0204 | 697 | 1425 |
| DejaVu Sans | bold_italic | Ölwanne Größe 12,5 mm | 10 | 417.911 | 419.707 | +0.430 | 0.0703 | 702 | 1425 |
| DejaVu Sans | bold_italic | Ölwanne Größe 12,5 mm | 50 | 10470.923 | 10492.669 | +0.208 | 0.2435 | 896 | 1425 |
| DejaVu Sans | bold_italic | AVATAR Toyota WAVE | 3 | 36.710 | 36.776 | +0.180 | 0.0173 | 342 | 614 |
| DejaVu Sans | bold_italic | AVATAR Toyota WAVE | 10 | 407.891 | 408.626 | +0.180 | 0.0576 | 342 | 614 |
| DejaVu Sans | bold_italic | AVATAR Toyota WAVE | 50 | 10207.396 | 10215.651 | +0.081 | 0.2276 | 419 | 614 |
| DejaVu Sans | bold_italic | Mama illu &%8 | 3 | 23.722 | 23.872 | +0.632 | 0.0176 | 443 | 893 |
| DejaVu Sans | bold_italic | Mama illu &%8 | 10 | 263.581 | 265.247 | +0.632 | 0.0588 | 443 | 893 |
| DejaVu Sans | bold_italic | Mama illu &%8 | 50 | 6610.434 | 6631.176 | +0.314 | 0.2519 | 578 | 893 |
| DejaVu Serif | regular | SOLIDON3D | 3 | 12.397 | 12.418 | +0.170 | 0.0243 | 308 | 896 |
| DejaVu Serif | regular | SOLIDON3D | 10 | 138.401 | 137.975 | -0.308 | 0.0786 | 320 | 896 |
| DejaVu Serif | regular | SOLIDON3D | 50 | 3445.175 | 3449.383 | +0.122 | 0.2236 | 474 | 896 |
| DejaVu Serif | regular | Deckel 120 x 80 | 3 | 13.494 | 13.679 | +1.369 | 0.0242 | 389 | 1110 |
| DejaVu Serif | regular | Deckel 120 x 80 | 10 | 150.507 | 151.986 | +0.983 | 0.0780 | 402 | 1110 |
| DejaVu Serif | regular | Deckel 120 x 80 | 50 | 3793.394 | 3799.656 | +0.165 | 0.2234 | 592 | 1110 |
| DejaVu Serif | regular | Ölwanne Größe 12,5 mm | 3 | 20.799 | 20.928 | +0.618 | 0.0238 | 733 | 1653 |
| DejaVu Serif | regular | Ölwanne Größe 12,5 mm | 10 | 231.469 | 232.530 | +0.458 | 0.0758 | 740 | 1653 |
| DejaVu Serif | regular | Ölwanne Größe 12,5 mm | 50 | 5805.968 | 5813.253 | +0.125 | 0.2167 | 996 | 1653 |
| DejaVu Serif | regular | AVATAR Toyota WAVE | 3 | 20.342 | 20.414 | +0.351 | 0.0167 | 426 | 730 |
| DejaVu Serif | regular | AVATAR Toyota WAVE | 10 | 226.028 | 226.822 | +0.351 | 0.0556 | 426 | 730 |
| DejaVu Serif | regular | AVATAR Toyota WAVE | 50 | 5668.248 | 5670.545 | +0.041 | 0.2214 | 518 | 730 |
| DejaVu Serif | regular | Mama illu &%8 | 3 | 13.998 | 14.083 | +0.601 | 0.0162 | 483 | 1000 |
| DejaVu Serif | regular | Mama illu &%8 | 10 | 155.539 | 156.474 | +0.601 | 0.0540 | 483 | 1000 |
| DejaVu Serif | regular | Mama illu &%8 | 50 | 3898.953 | 3911.851 | +0.331 | 0.2211 | 626 | 1000 |
| DejaVu Serif | bold | SOLIDON3D | 3 | 19.781 | 20.006 | +1.133 | 0.0248 | 284 | 904 |
| DejaVu Serif | bold | SOLIDON3D | 10 | 221.179 | 222.284 | +0.499 | 0.0794 | 308 | 904 |
| DejaVu Serif | bold | SOLIDON3D | 50 | 5549.468 | 5557.090 | +0.137 | 0.2544 | 455 | 904 |
| DejaVu Serif | bold | Deckel 120 x 80 | 3 | 21.948 | 22.237 | +1.314 | 0.0249 | 391 | 1162 |
| DejaVu Serif | bold | Deckel 120 x 80 | 10 | 244.455 | 247.074 | +1.071 | 0.0797 | 403 | 1162 |
| DejaVu Serif | bold | Deckel 120 x 80 | 50 | 6166.164 | 6176.839 | +0.173 | 0.2214 | 600 | 1162 |
| DejaVu Serif | bold | Ölwanne Größe 12,5 mm | 3 | 33.498 | 33.795 | +0.888 | 0.0244 | 724 | 1685 |
| DejaVu Serif | bold | Ölwanne Größe 12,5 mm | 10 | 372.896 | 375.502 | +0.699 | 0.0788 | 736 | 1685 |
| DejaVu Serif | bold | Ölwanne Größe 12,5 mm | 50 | 9371.364 | 9387.558 | +0.173 | 0.2301 | 1032 | 1685 |
| DejaVu Serif | bold | AVATAR Toyota WAVE | 3 | 30.696 | 30.814 | +0.382 | 0.0191 | 426 | 755 |
| DejaVu Serif | bold | AVATAR Toyota WAVE | 10 | 341.069 | 342.372 | +0.382 | 0.0636 | 426 | 755 |
| DejaVu Serif | bold | AVATAR Toyota WAVE | 50 | 8554.173 | 8559.311 | +0.060 | 0.2558 | 531 | 755 |
| DejaVu Serif | bold | Mama illu &%8 | 3 | 22.189 | 22.330 | +0.637 | 0.0170 | 483 | 1025 |
| DejaVu Serif | bold | Mama illu &%8 | 10 | 246.543 | 248.113 | +0.637 | 0.0567 | 483 | 1025 |
| DejaVu Serif | bold | Mama illu &%8 | 50 | 6183.798 | 6202.826 | +0.308 | 0.2336 | 633 | 1025 |
| DejaVu Serif | italic | SOLIDON3D | 3 | 12.402 | 12.420 | +0.139 | 0.0268 | 308 | 894 |
| DejaVu Serif | italic | SOLIDON3D | 10 | 138.269 | 137.995 | -0.198 | 0.0837 | 326 | 894 |
| DejaVu Serif | italic | SOLIDON3D | 50 | 3445.909 | 3449.870 | +0.115 | 0.2420 | 472 | 894 |
| DejaVu Serif | italic | Deckel 120 x 80 | 3 | 13.058 | 13.257 | +1.526 | 0.0430 | 383 | 1155 |
| DejaVu Serif | italic | Deckel 120 x 80 | 10 | 145.737 | 147.298 | +1.071 | 0.1345 | 402 | 1155 |
| DejaVu Serif | italic | Deckel 120 x 80 | 50 | 3671.660 | 3682.450 | +0.294 | 0.2498 | 590 | 1155 |
| DejaVu Serif | italic | Ölwanne Größe 12,5 mm | 3 | 20.104 | 20.247 | +0.710 | 0.0426 | 727 | 1725 |
| DejaVu Serif | italic | Ölwanne Größe 12,5 mm | 10 | 223.823 | 224.966 | +0.510 | 0.1336 | 745 | 1725 |
| DejaVu Serif | italic | Ölwanne Größe 12,5 mm | 50 | 5612.397 | 5624.139 | +0.209 | 0.2543 | 984 | 1725 |
| DejaVu Serif | italic | AVATAR Toyota WAVE | 3 | 20.400 | 20.474 | +0.360 | 0.0245 | 428 | 766 |
| DejaVu Serif | italic | AVATAR Toyota WAVE | 10 | 226.725 | 227.488 | +0.336 | 0.0852 | 431 | 766 |
| DejaVu Serif | italic | AVATAR Toyota WAVE | 50 | 5681.419 | 5687.188 | +0.102 | 0.2547 | 506 | 766 |
| DejaVu Serif | italic | Mama illu &%8 | 3 | 13.489 | 13.568 | +0.590 | 0.0244 | 454 | 956 |
| DejaVu Serif | italic | Mama illu &%8 | 10 | 149.980 | 150.757 | +0.518 | 0.0845 | 460 | 956 |
| DejaVu Serif | italic | Mama illu &%8 | 50 | 3759.787 | 3768.931 | +0.243 | 0.2321 | 593 | 956 |
| DejaVu Serif | bold_italic | SOLIDON3D | 3 | 19.782 | 20.005 | +1.130 | 0.0270 | 284 | 917 |
| DejaVu Serif | bold_italic | SOLIDON3D | 10 | 221.088 | 222.279 | +0.539 | 0.0833 | 312 | 917 |
| DejaVu Serif | bold_italic | SOLIDON3D | 50 | 5549.427 | 5556.979 | +0.136 | 0.2461 | 451 | 917 |
| DejaVu Serif | bold_italic | Deckel 120 x 80 | 3 | 21.471 | 21.775 | +1.417 | 0.0611 | 386 | 1196 |
| DejaVu Serif | bold_italic | Deckel 120 x 80 | 10 | 239.483 | 241.943 | +1.027 | 0.1621 | 408 | 1196 |
| DejaVu Serif | bold_italic | Deckel 120 x 80 | 50 | 6033.888 | 6048.583 | +0.244 | 0.2381 | 593 | 1196 |
| DejaVu Serif | bold_italic | Ölwanne Größe 12,5 mm | 3 | 32.961 | 33.279 | +0.965 | 0.0613 | 715 | 1756 |
| DejaVu Serif | bold_italic | Ölwanne Größe 12,5 mm | 10 | 367.073 | 369.770 | +0.735 | 0.1626 | 737 | 1756 |
| DejaVu Serif | bold_italic | Ölwanne Größe 12,5 mm | 50 | 9225.114 | 9244.258 | +0.208 | 0.2187 | 1019 | 1756 |
| DejaVu Serif | bold_italic | AVATAR Toyota WAVE | 3 | 30.871 | 30.997 | +0.410 | 0.0249 | 428 | 788 |
| DejaVu Serif | bold_italic | AVATAR Toyota WAVE | 10 | 343.124 | 344.412 | +0.375 | 0.0723 | 430 | 788 |
| DejaVu Serif | bold_italic | AVATAR Toyota WAVE | 50 | 8603.047 | 8610.295 | +0.084 | 0.2360 | 522 | 788 |
| DejaVu Serif | bold_italic | Mama illu &%8 | 3 | 21.724 | 21.874 | +0.690 | 0.0215 | 449 | 991 |
| DejaVu Serif | bold_italic | Mama illu &%8 | 10 | 241.485 | 243.048 | +0.647 | 0.0703 | 451 | 991 |
| DejaVu Serif | bold_italic | Mama illu &%8 | 50 | 6058.850 | 6076.205 | +0.286 | 0.2438 | 588 | 991 |
| DejaVu Sans Mono | regular | SOLIDON3D | 3 | 12.135 | 12.279 | +1.183 | 0.0231 | 254 | 803 |
| DejaVu Sans Mono | regular | SOLIDON3D | 10 | 135.497 | 136.433 | +0.690 | 0.0711 | 270 | 803 |
| DejaVu Sans Mono | regular | SOLIDON3D | 50 | 3407.541 | 3410.813 | +0.096 | 0.2557 | 384 | 803 |
| DejaVu Sans Mono | regular | Deckel 120 x 80 | 3 | 14.295 | 14.486 | +1.338 | 0.0229 | 399 | 1108 |
| DejaVu Sans Mono | regular | Deckel 120 x 80 | 10 | 159.298 | 160.959 | +1.042 | 0.0709 | 411 | 1108 |
| DejaVu Sans Mono | regular | Deckel 120 x 80 | 50 | 4014.875 | 4023.963 | +0.226 | 0.2279 | 592 | 1108 |
| DejaVu Sans Mono | regular | Ölwanne Größe 12,5 mm | 3 | 20.396 | 20.576 | +0.882 | 0.0208 | 611 | 1469 |
| DejaVu Sans Mono | regular | Ölwanne Größe 12,5 mm | 10 | 226.858 | 228.626 | +0.779 | 0.0720 | 617 | 1469 |
| DejaVu Sans Mono | regular | Ölwanne Größe 12,5 mm | 50 | 5707.833 | 5715.640 | +0.137 | 0.2531 | 822 | 1469 |
| DejaVu Sans Mono | regular | AVATAR Toyota WAVE | 3 | 19.887 | 19.961 | +0.372 | 0.0176 | 318 | 637 |
| DejaVu Sans Mono | regular | AVATAR Toyota WAVE | 10 | 220.968 | 221.790 | +0.372 | 0.0587 | 318 | 637 |
| DejaVu Sans Mono | regular | AVATAR Toyota WAVE | 50 | 5541.758 | 5544.759 | +0.054 | 0.2035 | 410 | 637 |
| DejaVu Sans Mono | regular | Mama illu &%8 | 3 | 13.141 | 13.212 | +0.544 | 0.0144 | 464 | 925 |
| DejaVu Sans Mono | regular | Mama illu &%8 | 10 | 146.007 | 146.801 | +0.544 | 0.0479 | 464 | 925 |
| DejaVu Sans Mono | regular | Mama illu &%8 | 50 | 3657.285 | 3670.026 | +0.348 | 0.2270 | 595 | 925 |
| DejaVu Sans Mono | bold | SOLIDON3D | 3 | 16.860 | 17.068 | +1.233 | 0.0238 | 254 | 746 |
| DejaVu Sans Mono | bold | SOLIDON3D | 10 | 188.022 | 189.647 | +0.865 | 0.0710 | 270 | 746 |
| DejaVu Sans Mono | bold | SOLIDON3D | 50 | 4731.526 | 4741.184 | +0.204 | 0.2411 | 374 | 746 |
| DejaVu Sans Mono | bold | Deckel 120 x 80 | 3 | 20.190 | 20.454 | +1.306 | 0.0236 | 396 | 1044 |
| DejaVu Sans Mono | bold | Deckel 120 x 80 | 10 | 224.811 | 227.265 | +1.092 | 0.0705 | 408 | 1044 |
| DejaVu Sans Mono | bold | Deckel 120 x 80 | 50 | 5665.903 | 5681.625 | +0.277 | 0.2283 | 564 | 1044 |
| DejaVu Sans Mono | bold | Ölwanne Größe 12,5 mm | 3 | 29.062 | 29.336 | +0.941 | 0.0212 | 608 | 1367 |
| DejaVu Sans Mono | bold | Ölwanne Größe 12,5 mm | 10 | 323.152 | 325.952 | +0.867 | 0.0724 | 614 | 1367 |
| DejaVu Sans Mono | bold | Ölwanne Größe 12,5 mm | 50 | 8129.723 | 8148.796 | +0.235 | 0.2579 | 815 | 1367 |
| DejaVu Sans Mono | bold | AVATAR Toyota WAVE | 3 | 27.878 | 27.989 | +0.397 | 0.0174 | 310 | 586 |
| DejaVu Sans Mono | bold | AVATAR Toyota WAVE | 10 | 309.755 | 310.986 | +0.397 | 0.0578 | 310 | 586 |
| DejaVu Sans Mono | bold | AVATAR Toyota WAVE | 50 | 7767.515 | 7774.651 | +0.092 | 0.2119 | 402 | 586 |
| DejaVu Sans Mono | bold | Mama illu &%8 | 3 | 18.422 | 18.556 | +0.729 | 0.0162 | 447 | 861 |
| DejaVu Sans Mono | bold | Mama illu &%8 | 10 | 204.686 | 206.179 | +0.729 | 0.0539 | 447 | 861 |
| DejaVu Sans Mono | bold | Mama illu &%8 | 50 | 5133.514 | 5154.471 | +0.408 | 0.2274 | 581 | 861 |
| DejaVu Sans Mono | italic | SOLIDON3D | 3 | 12.184 | 12.260 | +0.629 | 0.0176 | 318 | 778 |
| DejaVu Sans Mono | italic | SOLIDON3D | 10 | 135.376 | 136.226 | +0.629 | 0.0587 | 318 | 778 |
| DejaVu Sans Mono | italic | SOLIDON3D | 50 | 3398.019 | 3405.659 | +0.225 | 0.2165 | 418 | 778 |
| DejaVu Sans Mono | italic | Deckel 120 x 80 | 3 | 14.534 | 14.623 | +0.615 | 0.0334 | 480 | 1087 |
| DejaVu Sans Mono | italic | Deckel 120 x 80 | 10 | 161.406 | 162.480 | +0.665 | 0.0782 | 481 | 1087 |
| DejaVu Sans Mono | italic | Deckel 120 x 80 | 50 | 4046.214 | 4061.998 | +0.390 | 0.2421 | 636 | 1087 |
| DejaVu Sans Mono | italic | Ölwanne Größe 12,5 mm | 3 | 20.492 | 20.543 | +0.250 | 0.0338 | 751 | 1451 |
| DejaVu Sans Mono | italic | Ölwanne Größe 12,5 mm | 10 | 227.603 | 228.254 | +0.286 | 0.0792 | 752 | 1451 |
| DejaVu Sans Mono | italic | Ölwanne Größe 12,5 mm | 50 | 5695.295 | 5706.360 | +0.194 | 0.2381 | 920 | 1451 |
| DejaVu Sans Mono | italic | AVATAR Toyota WAVE | 3 | 19.908 | 19.925 | +0.089 | 0.0163 | 350 | 631 |
| DejaVu Sans Mono | italic | AVATAR Toyota WAVE | 10 | 221.196 | 221.394 | +0.089 | 0.0542 | 350 | 631 |
| DejaVu Sans Mono | italic | AVATAR Toyota WAVE | 50 | 5530.222 | 5534.856 | +0.084 | 0.2083 | 421 | 631 |
| DejaVu Sans Mono | italic | Mama illu &%8 | 3 | 13.125 | 13.208 | +0.628 | 0.0156 | 506 | 915 |
| DejaVu Sans Mono | italic | Mama illu &%8 | 10 | 145.837 | 146.752 | +0.628 | 0.0519 | 506 | 915 |
| DejaVu Sans Mono | italic | Mama illu &%8 | 50 | 3656.337 | 3668.812 | +0.341 | 0.2418 | 641 | 915 |
| DejaVu Sans Mono | bold_italic | SOLIDON3D | 3 | 16.915 | 17.033 | +0.697 | 0.0173 | 325 | 735 |
| DejaVu Sans Mono | bold_italic | SOLIDON3D | 10 | 187.946 | 189.257 | +0.697 | 0.0576 | 325 | 735 |
| DejaVu Sans Mono | bold_italic | SOLIDON3D | 50 | 4717.751 | 4731.426 | +0.290 | 0.2336 | 416 | 735 |
| DejaVu Sans Mono | bold_italic | Deckel 120 x 80 | 3 | 20.206 | 20.372 | +0.821 | 0.0343 | 472 | 1018 |
| DejaVu Sans Mono | bold_italic | Deckel 120 x 80 | 10 | 224.682 | 226.354 | +0.744 | 0.0894 | 475 | 1018 |
| DejaVu Sans Mono | bold_italic | Deckel 120 x 80 | 50 | 5637.848 | 5658.844 | +0.372 | 0.2229 | 605 | 1018 |
| DejaVu Sans Mono | bold_italic | Ölwanne Größe 12,5 mm | 3 | 29.072 | 29.266 | +0.665 | 0.0347 | 720 | 1350 |
| DejaVu Sans Mono | bold_italic | Ölwanne Größe 12,5 mm | 10 | 323.224 | 325.174 | +0.603 | 0.0905 | 724 | 1350 |
| DejaVu Sans Mono | bold_italic | Ölwanne Größe 12,5 mm | 50 | 8107.553 | 8129.361 | +0.269 | 0.2339 | 888 | 1350 |
| DejaVu Sans Mono | bold_italic | AVATAR Toyota WAVE | 3 | 27.811 | 27.914 | +0.370 | 0.0200 | 325 | 588 |
| DejaVu Sans Mono | bold_italic | AVATAR Toyota WAVE | 10 | 309.175 | 310.159 | +0.318 | 0.0651 | 329 | 588 |
| DejaVu Sans Mono | bold_italic | AVATAR Toyota WAVE | 50 | 7746.274 | 7753.984 | +0.100 | 0.2183 | 405 | 588 |
| DejaVu Sans Mono | bold_italic | Mama illu &%8 | 3 | 18.361 | 18.481 | +0.651 | 0.0166 | 488 | 858 |
| DejaVu Sans Mono | bold_italic | Mama illu &%8 | 10 | 204.013 | 205.341 | +0.651 | 0.0553 | 488 | 858 |
| DejaVu Sans Mono | bold_italic | Mama illu &%8 | 50 | 5115.986 | 5133.529 | +0.343 | 0.2209 | 619 | 858 |
| Liberation Sans | regular | SOLIDON3D | 3 | 11.517 | 11.601 | +0.728 | 0.0511 | 283 | 829 |
| Liberation Sans | regular | SOLIDON3D | 10 | 128.431 | 128.897 | +0.363 | 0.1590 | 293 | 829 |
| Liberation Sans | regular | SOLIDON3D | 50 | 3209.539 | 3222.420 | +0.401 | 0.2474 | 429 | 829 |
| Liberation Sans | regular | Deckel 120 x 80 | 3 | 12.663 | 12.878 | +1.702 | 0.0666 | 353 | 1025 |
| Liberation Sans | regular | Deckel 120 x 80 | 10 | 141.086 | 143.093 | +1.423 | 0.2218 | 367 | 1025 |
| Liberation Sans | regular | Deckel 120 x 80 | 50 | 3568.536 | 3577.328 | +0.246 | 0.2619 | 534 | 1025 |
| Liberation Sans | regular | Ölwanne Größe 12,5 mm | 3 | 19.514 | 19.760 | +1.263 | 0.0674 | 664 | 1587 |
| Liberation Sans | regular | Ölwanne Größe 12,5 mm | 10 | 217.187 | 219.558 | +1.092 | 0.2247 | 672 | 1587 |
| Liberation Sans | regular | Ölwanne Größe 12,5 mm | 50 | 5468.792 | 5488.960 | +0.369 | 0.2665 | 911 | 1587 |
| Liberation Sans | regular | AVATAR Toyota WAVE | 3 | 18.912 | 19.048 | +0.721 | 0.0664 | 367 | 818 |
| Liberation Sans | regular | AVATAR Toyota WAVE | 10 | 210.228 | 211.649 | +0.676 | 0.2214 | 370 | 818 |
| Liberation Sans | regular | AVATAR Toyota WAVE | 50 | 5283.460 | 5291.223 | +0.147 | 0.2091 | 455 | 818 |
| Liberation Sans | regular | Mama illu &%8 | 3 | 12.712 | 12.834 | +0.962 | 0.0403 | 477 | 1061 |
| Liberation Sans | regular | Mama illu &%8 | 10 | 141.339 | 142.604 | +0.895 | 0.1289 | 483 | 1061 |
| Liberation Sans | regular | Mama illu &%8 | 50 | 3546.976 | 3565.105 | +0.511 | 0.2185 | 640 | 1061 |
| Liberation Sans | bold | SOLIDON3D | 3 | 16.635 | 16.786 | +0.909 | 0.0328 | 265 | 799 |
| Liberation Sans | bold | SOLIDON3D | 10 | 185.489 | 186.513 | +0.552 | 0.0948 | 284 | 799 |
| Liberation Sans | bold | SOLIDON3D | 50 | 4656.340 | 4662.819 | +0.139 | 0.2287 | 395 | 799 |
| Liberation Sans | bold | Deckel 120 x 80 | 3 | 18.142 | 18.410 | +1.478 | 0.0727 | 359 | 980 |
| Liberation Sans | bold | Deckel 120 x 80 | 10 | 202.115 | 204.553 | +1.206 | 0.1259 | 375 | 980 |
| Liberation Sans | bold | Deckel 120 x 80 | 50 | 5094.925 | 5113.832 | +0.371 | 0.2477 | 541 | 980 |
| Liberation Sans | bold | Ölwanne Größe 12,5 mm | 3 | 28.311 | 28.593 | +0.997 | 0.0472 | 642 | 1503 |
| Liberation Sans | bold | Ölwanne Größe 12,5 mm | 10 | 315.070 | 317.700 | +0.835 | 0.1511 | 667 | 1503 |
| Liberation Sans | bold | Ölwanne Größe 12,5 mm | 50 | 7922.122 | 7942.508 | +0.257 | 0.2323 | 893 | 1503 |
| Liberation Sans | bold | AVATAR Toyota WAVE | 3 | 27.433 | 27.499 | +0.242 | 0.0409 | 366 | 795 |
| Liberation Sans | bold | AVATAR Toyota WAVE | 10 | 304.524 | 305.546 | +0.336 | 0.1278 | 372 | 795 |
| Liberation Sans | bold | AVATAR Toyota WAVE | 50 | 7629.673 | 7638.662 | +0.118 | 0.2000 | 459 | 795 |
| Liberation Sans | bold | Mama illu &%8 | 3 | 18.243 | 18.372 | +0.703 | 0.0298 | 471 | 1018 |
| Liberation Sans | bold | Mama illu &%8 | 10 | 202.622 | 204.129 | +0.744 | 0.0963 | 480 | 1018 |
| Liberation Sans | bold | Mama illu &%8 | 50 | 5079.348 | 5103.215 | +0.470 | 0.2316 | 631 | 1018 |
| Liberation Sans | italic | SOLIDON3D | 3 | 11.310 | 11.404 | +0.836 | 0.0404 | 283 | 836 |
| Liberation Sans | italic | SOLIDON3D | 10 | 125.674 | 126.713 | +0.827 | 0.1191 | 286 | 836 |
| Liberation Sans | italic | SOLIDON3D | 50 | 3163.325 | 3167.822 | +0.142 | 0.2389 | 419 | 836 |
| Liberation Sans | italic | Deckel 120 x 80 | 3 | 12.719 | 12.830 | +0.871 | 0.0336 | 398 | 1012 |
| Liberation Sans | italic | Deckel 120 x 80 | 10 | 141.358 | 142.550 | +0.843 | 0.1169 | 402 | 1012 |
| Liberation Sans | italic | Deckel 120 x 80 | 50 | 3547.602 | 3563.751 | +0.455 | 0.2344 | 552 | 1012 |
| Liberation Sans | italic | Ölwanne Größe 12,5 mm | 3 | 19.514 | 19.652 | +0.708 | 0.0364 | 708 | 1606 |
| Liberation Sans | italic | Ölwanne Größe 12,5 mm | 10 | 216.819 | 218.360 | +0.711 | 0.1250 | 712 | 1606 |
| Liberation Sans | italic | Ölwanne Größe 12,5 mm | 50 | 5442.275 | 5459.007 | +0.307 | 0.2355 | 927 | 1606 |
| Liberation Sans | italic | AVATAR Toyota WAVE | 3 | 18.903 | 18.940 | +0.199 | 0.0313 | 394 | 867 |
| Liberation Sans | italic | AVATAR Toyota WAVE | 10 | 209.926 | 210.449 | +0.249 | 0.1138 | 396 | 867 |
| Liberation Sans | italic | AVATAR Toyota WAVE | 50 | 5251.983 | 5261.230 | +0.176 | 0.2236 | 465 | 867 |
| Liberation Sans | italic | Mama illu &%8 | 3 | 12.730 | 12.806 | +0.592 | 0.0202 | 517 | 1099 |
| Liberation Sans | italic | Mama illu &%8 | 10 | 141.389 | 142.285 | +0.633 | 0.0735 | 520 | 1099 |
| Liberation Sans | italic | Mama illu &%8 | 50 | 3543.593 | 3557.116 | +0.382 | 0.2254 | 668 | 1099 |
| Liberation Sans | bold_italic | SOLIDON3D | 3 | 16.370 | 16.513 | +0.872 | 0.0408 | 280 | 784 |
| Liberation Sans | bold_italic | SOLIDON3D | 10 | 181.967 | 183.473 | +0.828 | 0.1430 | 286 | 784 |
| Liberation Sans | bold_italic | SOLIDON3D | 50 | 4572.108 | 4586.832 | +0.322 | 0.2099 | 411 | 784 |
| Liberation Sans | bold_italic | Deckel 120 x 80 | 3 | 18.201 | 18.450 | +1.368 | 0.0638 | 375 | 981 |
| Liberation Sans | bold_italic | Deckel 120 x 80 | 10 | 202.464 | 205.002 | +1.253 | 0.2127 | 387 | 981 |
| Liberation Sans | bold_italic | Deckel 120 x 80 | 50 | 5097.914 | 5125.051 | +0.532 | 0.2493 | 531 | 981 |
| Liberation Sans | bold_italic | Ölwanne Größe 12,5 mm | 3 | 28.513 | 28.672 | +0.557 | 0.0288 | 703 | 1485 |
| Liberation Sans | bold_italic | Ölwanne Größe 12,5 mm | 10 | 316.713 | 318.573 | +0.587 | 0.0945 | 706 | 1485 |
| Liberation Sans | bold_italic | Ölwanne Größe 12,5 mm | 50 | 7937.253 | 7964.316 | +0.341 | 0.2510 | 911 | 1485 |
| Liberation Sans | bold_italic | AVATAR Toyota WAVE | 3 | 27.479 | 27.532 | +0.193 | 0.0291 | 390 | 837 |
| Liberation Sans | bold_italic | AVATAR Toyota WAVE | 10 | 305.168 | 305.914 | +0.244 | 0.0953 | 394 | 837 |
| Liberation Sans | bold_italic | AVATAR Toyota WAVE | 50 | 7634.017 | 7647.840 | +0.181 | 0.2370 | 463 | 837 |
| Liberation Sans | bold_italic | Mama illu &%8 | 3 | 18.089 | 18.242 | +0.848 | 0.0416 | 512 | 1059 |
| Liberation Sans | bold_italic | Mama illu &%8 | 10 | 201.259 | 202.690 | +0.711 | 0.1385 | 516 | 1059 |
| Liberation Sans | bold_italic | Mama illu &%8 | 50 | 5048.168 | 5067.251 | +0.378 | 0.2329 | 665 | 1059 |
| Liberation Serif | regular | SOLIDON3D | 3 | 9.614 | 9.801 | +1.948 | 0.0858 | 298 | 856 |
| Liberation Serif | regular | SOLIDON3D | 10 | 108.540 | 108.904 | +0.335 | 0.1601 | 323 | 856 |
| Liberation Serif | regular | SOLIDON3D | 50 | 2718.693 | 2722.607 | +0.144 | 0.2265 | 453 | 856 |
| Liberation Serif | regular | Deckel 120 x 80 | 3 | 9.843 | 10.085 | +2.452 | 0.0672 | 382 | 1020 |
| Liberation Serif | regular | Deckel 120 x 80 | 10 | 110.434 | 112.051 | +1.464 | 0.2031 | 397 | 1020 |
| Liberation Serif | regular | Deckel 120 x 80 | 50 | 2789.336 | 2801.286 | +0.428 | 0.2389 | 531 | 1020 |
| Liberation Serif | regular | Ölwanne Größe 12,5 mm | 3 | 14.981 | 15.232 | +1.674 | 0.0859 | 711 | 1445 |
| Liberation Serif | regular | Ölwanne Größe 12,5 mm | 10 | 167.677 | 169.240 | +0.933 | 0.1969 | 734 | 1445 |
| Liberation Serif | regular | Ölwanne Größe 12,5 mm | 50 | 4213.081 | 4231.009 | +0.426 | 0.2295 | 907 | 1445 |
| Liberation Serif | regular | AVATAR Toyota WAVE | 3 | 15.311 | 15.421 | +0.717 | 0.0561 | 421 | 725 |
| Liberation Serif | regular | AVATAR Toyota WAVE | 10 | 170.480 | 171.344 | +0.507 | 0.1973 | 425 | 725 |
| Liberation Serif | regular | AVATAR Toyota WAVE | 50 | 4277.158 | 4283.596 | +0.151 | 0.2168 | 485 | 725 |
| Liberation Serif | regular | Mama illu &%8 | 3 | 10.722 | 10.869 | +1.373 | 0.0481 | 456 | 915 |
| Liberation Serif | regular | Mama illu &%8 | 10 | 119.622 | 120.768 | +0.959 | 0.1738 | 469 | 915 |
| Liberation Serif | regular | Mama illu &%8 | 50 | 3007.268 | 3019.212 | +0.397 | 0.2493 | 593 | 915 |
| Liberation Serif | bold | SOLIDON3D | 3 | 13.875 | 14.162 | +2.068 | 0.0888 | 284 | 831 |
| Liberation Serif | bold | SOLIDON3D | 10 | 156.139 | 157.352 | +0.777 | 0.1951 | 312 | 831 |
| Liberation Serif | bold | SOLIDON3D | 50 | 3929.831 | 3933.808 | +0.101 | 0.2336 | 427 | 831 |
| Liberation Serif | bold | Deckel 120 x 80 | 3 | 14.605 | 14.852 | +1.690 | 0.0673 | 401 | 988 |
| Liberation Serif | bold | Deckel 120 x 80 | 10 | 163.032 | 165.022 | +1.220 | 0.1732 | 412 | 988 |
| Liberation Serif | bold | Deckel 120 x 80 | 50 | 4107.376 | 4125.544 | +0.442 | 0.2180 | 536 | 988 |
| Liberation Serif | bold | Ölwanne Größe 12,5 mm | 3 | 22.693 | 23.001 | +1.357 | 0.0888 | 702 | 1459 |
| Liberation Serif | bold | Ölwanne Größe 12,5 mm | 10 | 253.324 | 255.564 | +0.885 | 0.1847 | 721 | 1459 |
| Liberation Serif | bold | Ölwanne Größe 12,5 mm | 50 | 6366.005 | 6389.111 | +0.363 | 0.2323 | 874 | 1459 |
| Liberation Serif | bold | AVATAR Toyota WAVE | 3 | 22.311 | 22.408 | +0.432 | 0.0389 | 421 | 723 |
| Liberation Serif | bold | AVATAR Toyota WAVE | 10 | 248.070 | 248.972 | +0.364 | 0.1271 | 425 | 723 |
| Liberation Serif | bold | AVATAR Toyota WAVE | 50 | 6215.074 | 6224.310 | +0.149 | 0.2344 | 485 | 723 |
| Liberation Serif | bold | Mama illu &%8 | 3 | 15.778 | 16.002 | +1.417 | 0.0495 | 447 | 879 |
| Liberation Serif | bold | Mama illu &%8 | 10 | 176.042 | 177.801 | +0.999 | 0.1715 | 459 | 879 |
| Liberation Serif | bold | Mama illu &%8 | 50 | 4428.117 | 4445.023 | +0.382 | 0.2229 | 578 | 879 |
| Liberation Serif | italic | SOLIDON3D | 3 | 9.583 | 9.568 | -0.160 | 0.0626 | 326 | 798 |
| Liberation Serif | italic | SOLIDON3D | 10 | 106.423 | 106.313 | -0.103 | 0.2088 | 331 | 798 |
| Liberation Serif | italic | SOLIDON3D | 50 | 2653.058 | 2657.819 | +0.179 | 0.2278 | 432 | 798 |
| Liberation Serif | italic | Deckel 120 x 80 | 3 | 9.635 | 9.780 | +1.511 | 0.0625 | 414 | 1041 |
| Liberation Serif | italic | Deckel 120 x 80 | 10 | 107.507 | 108.672 | +1.084 | 0.2083 | 429 | 1041 |
| Liberation Serif | italic | Deckel 120 x 80 | 50 | 2703.059 | 2716.800 | +0.508 | 0.2267 | 568 | 1041 |
| Liberation Serif | italic | Ölwanne Größe 12,5 mm | 3 | 14.716 | 14.808 | +0.621 | 0.0332 | 751 | 1518 |
| Liberation Serif | italic | Ölwanne Größe 12,5 mm | 10 | 163.492 | 164.530 | +0.635 | 0.1121 | 754 | 1518 |
| Liberation Serif | italic | Ölwanne Größe 12,5 mm | 50 | 4100.737 | 4113.250 | +0.305 | 0.2147 | 925 | 1518 |
| Liberation Serif | italic | AVATAR Toyota WAVE | 3 | 15.099 | 15.129 | +0.200 | 0.0380 | 430 | 717 |
| Liberation Serif | italic | AVATAR Toyota WAVE | 10 | 167.801 | 168.105 | +0.181 | 0.1293 | 432 | 717 |
| Liberation Serif | italic | AVATAR Toyota WAVE | 50 | 4198.684 | 4202.633 | +0.094 | 0.2221 | 500 | 717 |
| Liberation Serif | italic | Mama illu &%8 | 3 | 10.636 | 10.792 | +1.467 | 0.0576 | 458 | 935 |
| Liberation Serif | italic | Mama illu &%8 | 10 | 118.723 | 119.913 | +1.002 | 0.2045 | 470 | 935 |
| Liberation Serif | italic | Mama illu &%8 | 50 | 2987.568 | 2997.820 | +0.343 | 0.2194 | 589 | 935 |
| Liberation Serif | bold_italic | SOLIDON3D | 3 | 13.283 | 13.289 | +0.046 | 0.0521 | 318 | 774 |
| Liberation Serif | bold_italic | SOLIDON3D | 10 | 147.258 | 147.652 | +0.267 | 0.1844 | 325 | 774 |
| Liberation Serif | bold_italic | SOLIDON3D | 50 | 3683.076 | 3691.294 | +0.223 | 0.2399 | 429 | 774 |
| Liberation Serif | bold_italic | Deckel 120 x 80 | 3 | 13.611 | 13.757 | +1.075 | 0.0566 | 415 | 993 |
| Liberation Serif | bold_italic | Deckel 120 x 80 | 10 | 151.532 | 152.857 | +0.875 | 0.2022 | 429 | 993 |
| Liberation Serif | bold_italic | Deckel 120 x 80 | 50 | 3806.049 | 3821.426 | +0.404 | 0.2171 | 558 | 993 |
| Liberation Serif | bold_italic | Ölwanne Größe 12,5 mm | 3 | 21.456 | 21.569 | +0.527 | 0.0272 | 724 | 1440 |
| Liberation Serif | bold_italic | Ölwanne Größe 12,5 mm | 10 | 238.343 | 239.654 | +0.550 | 0.0921 | 730 | 1440 |
| Liberation Serif | bold_italic | Ölwanne Größe 12,5 mm | 50 | 5975.102 | 5991.344 | +0.272 | 0.1995 | 912 | 1440 |
| Liberation Serif | bold_italic | AVATAR Toyota WAVE | 3 | 20.767 | 20.803 | +0.169 | 0.0245 | 450 | 694 |
| Liberation Serif | bold_italic | AVATAR Toyota WAVE | 10 | 230.703 | 231.139 | +0.189 | 0.0664 | 452 | 694 |
| Liberation Serif | bold_italic | AVATAR Toyota WAVE | 50 | 5772.416 | 5778.476 | +0.105 | 0.2248 | 512 | 694 |
| Liberation Serif | bold_italic | Mama illu &%8 | 3 | 14.981 | 15.137 | +1.042 | 0.0575 | 443 | 876 |
| Liberation Serif | bold_italic | Mama illu &%8 | 10 | 166.896 | 168.185 | +0.772 | 0.2043 | 451 | 876 |
| Liberation Serif | bold_italic | Mama illu &%8 | 50 | 4192.165 | 4204.637 | +0.297 | 0.2292 | 578 | 876 |
| Liberation Mono | regular | SOLIDON3D | 3 | 10.829 | 10.884 | +0.502 | 0.0562 | 265 | 795 |
| Liberation Mono | regular | SOLIDON3D | 10 | 120.358 | 120.928 | +0.474 | 0.1669 | 286 | 795 |
| Liberation Mono | regular | SOLIDON3D | 50 | 3020.005 | 3023.206 | +0.106 | 0.2516 | 404 | 795 |
| Liberation Mono | regular | Deckel 120 x 80 | 3 | 12.917 | 13.055 | +1.069 | 0.0356 | 381 | 1057 |
| Liberation Mono | regular | Deckel 120 x 80 | 10 | 143.725 | 145.054 | +0.925 | 0.1153 | 395 | 1057 |
| Liberation Mono | regular | Deckel 120 x 80 | 50 | 3620.636 | 3626.354 | +0.158 | 0.2618 | 575 | 1057 |
| Liberation Mono | regular | Ölwanne Größe 12,5 mm | 3 | 19.033 | 19.182 | +0.785 | 0.0588 | 647 | 1541 |
| Liberation Mono | regular | Ölwanne Größe 12,5 mm | 10 | 211.451 | 213.137 | +0.797 | 0.1804 | 665 | 1541 |
| Liberation Mono | regular | Ölwanne Größe 12,5 mm | 50 | 5315.897 | 5328.422 | +0.236 | 0.2571 | 890 | 1541 |
| Liberation Mono | regular | AVATAR Toyota WAVE | 3 | 17.588 | 17.696 | +0.612 | 0.0524 | 354 | 753 |
| Liberation Mono | regular | AVATAR Toyota WAVE | 10 | 195.576 | 196.623 | +0.535 | 0.1695 | 357 | 753 |
| Liberation Mono | regular | AVATAR Toyota WAVE | 50 | 4909.119 | 4915.568 | +0.131 | 0.2397 | 444 | 753 |
| Liberation Mono | regular | Mama illu &%8 | 3 | 12.223 | 12.409 | +1.528 | 0.0509 | 499 | 1030 |
| Liberation Mono | regular | Mama illu &%8 | 10 | 136.334 | 137.880 | +1.134 | 0.1662 | 508 | 1030 |
| Liberation Mono | regular | Mama illu &%8 | 50 | 3429.974 | 3447.010 | +0.497 | 0.2431 | 665 | 1030 |
| Liberation Mono | bold | SOLIDON3D | 3 | 15.531 | 15.614 | +0.538 | 0.0499 | 251 | 765 |
| Liberation Mono | bold | SOLIDON3D | 10 | 172.467 | 173.492 | +0.594 | 0.1550 | 273 | 765 |
| Liberation Mono | bold | SOLIDON3D | 50 | 4328.340 | 4337.298 | +0.207 | 0.2415 | 392 | 765 |
| Liberation Mono | bold | Deckel 120 x 80 | 3 | 18.264 | 18.454 | +1.042 | 0.0502 | 389 | 1002 |
| Liberation Mono | bold | Deckel 120 x 80 | 10 | 202.971 | 205.046 | +1.022 | 0.1569 | 407 | 1002 |
| Liberation Mono | bold | Deckel 120 x 80 | 50 | 5108.415 | 5126.138 | +0.347 | 0.2560 | 581 | 1002 |
| Liberation Mono | bold | Ölwanne Größe 12,5 mm | 3 | 26.486 | 26.811 | +1.229 | 0.0800 | 662 | 1509 |
| Liberation Mono | bold | Ölwanne Größe 12,5 mm | 10 | 294.808 | 297.900 | +1.049 | 0.2258 | 673 | 1509 |
| Liberation Mono | bold | Ölwanne Größe 12,5 mm | 50 | 7425.298 | 7447.490 | +0.299 | 0.2369 | 897 | 1509 |
| Liberation Mono | bold | AVATAR Toyota WAVE | 3 | 25.035 | 25.188 | +0.612 | 0.0680 | 376 | 805 |
| Liberation Mono | bold | AVATAR Toyota WAVE | 10 | 278.228 | 279.871 | +0.591 | 0.2266 | 378 | 805 |
| Liberation Mono | bold | AVATAR Toyota WAVE | 50 | 6987.049 | 6996.772 | +0.139 | 0.2247 | 458 | 805 |
| Liberation Mono | bold | Mama illu &%8 | 3 | 16.692 | 16.858 | +0.997 | 0.0417 | 486 | 996 |
| Liberation Mono | bold | Mama illu &%8 | 10 | 185.727 | 187.314 | +0.854 | 0.1415 | 495 | 996 |
| Liberation Mono | bold | Mama illu &%8 | 50 | 4661.991 | 4682.853 | +0.447 | 0.2533 | 639 | 996 |
| Liberation Mono | italic | SOLIDON3D | 3 | 10.814 | 10.881 | +0.615 | 0.0637 | 318 | 785 |
| Liberation Mono | italic | SOLIDON3D | 10 | 119.978 | 120.895 | +0.764 | 0.2124 | 325 | 785 |
| Liberation Mono | italic | SOLIDON3D | 50 | 3013.699 | 3022.377 | +0.288 | 0.2203 | 435 | 785 |
| Liberation Mono | italic | Deckel 120 x 80 | 3 | 12.927 | 13.036 | +0.840 | 0.0642 | 459 | 1059 |
| Liberation Mono | italic | Deckel 120 x 80 | 10 | 143.701 | 144.843 | +0.794 | 0.2139 | 465 | 1059 |
| Liberation Mono | italic | Deckel 120 x 80 | 50 | 3608.405 | 3621.074 | +0.351 | 0.2065 | 621 | 1059 |
| Liberation Mono | italic | Ölwanne Größe 12,5 mm | 3 | 19.004 | 19.160 | +0.818 | 0.0470 | 760 | 1559 |
| Liberation Mono | italic | Ölwanne Größe 12,5 mm | 10 | 211.385 | 212.889 | +0.711 | 0.1586 | 775 | 1559 |
| Liberation Mono | italic | Ölwanne Größe 12,5 mm | 50 | 5302.668 | 5322.214 | +0.369 | 0.2533 | 973 | 1559 |
| Liberation Mono | italic | AVATAR Toyota WAVE | 3 | 17.618 | 17.689 | +0.399 | 0.0483 | 397 | 828 |
| Liberation Mono | italic | AVATAR Toyota WAVE | 10 | 195.826 | 196.541 | +0.365 | 0.1546 | 402 | 828 |
| Liberation Mono | italic | AVATAR Toyota WAVE | 50 | 4903.706 | 4913.526 | +0.200 | 0.2533 | 477 | 828 |
| Liberation Mono | italic | Mama illu &%8 | 3 | 12.216 | 12.370 | +1.254 | 0.0470 | 579 | 1055 |
| Liberation Mono | italic | Mama illu &%8 | 10 | 136.198 | 137.440 | +0.912 | 0.1516 | 589 | 1055 |
| Liberation Mono | italic | Mama illu &%8 | 50 | 3423.185 | 3436.001 | +0.374 | 0.2346 | 727 | 1055 |
| Liberation Mono | bold_italic | SOLIDON3D | 3 | 15.547 | 15.592 | +0.287 | 0.0638 | 299 | 758 |
| Liberation Mono | bold_italic | SOLIDON3D | 10 | 172.320 | 173.241 | +0.534 | 0.2127 | 308 | 758 |
| Liberation Mono | bold_italic | SOLIDON3D | 50 | 4318.995 | 4331.016 | +0.278 | 0.2289 | 414 | 758 |
| Liberation Mono | bold_italic | Deckel 120 x 80 | 3 | 18.317 | 18.470 | +0.836 | 0.0643 | 441 | 1005 |
| Liberation Mono | bold_italic | Deckel 120 x 80 | 10 | 203.582 | 205.220 | +0.804 | 0.2143 | 447 | 1005 |
| Liberation Mono | bold_italic | Deckel 120 x 80 | 50 | 5110.078 | 5130.498 | +0.400 | 0.2125 | 596 | 1005 |
| Liberation Mono | bold_italic | Ölwanne Größe 12,5 mm | 3 | 26.603 | 26.828 | +0.845 | 0.0472 | 731 | 1496 |
| Liberation Mono | bold_italic | Ölwanne Größe 12,5 mm | 10 | 295.893 | 298.087 | +0.741 | 0.1670 | 745 | 1496 |
| Liberation Mono | bold_italic | Ölwanne Größe 12,5 mm | 50 | 7425.482 | 7452.165 | +0.359 | 0.2505 | 937 | 1496 |
| Liberation Mono | bold_italic | AVATAR Toyota WAVE | 3 | 25.046 | 25.186 | +0.561 | 0.0475 | 403 | 807 |
| Liberation Mono | bold_italic | AVATAR Toyota WAVE | 10 | 278.646 | 279.846 | +0.431 | 0.1678 | 410 | 807 |
| Liberation Mono | bold_italic | AVATAR Toyota WAVE | 50 | 6984.898 | 6996.147 | +0.161 | 0.2178 | 476 | 807 |
| Liberation Mono | bold_italic | Mama illu &%8 | 3 | 16.719 | 16.902 | +1.093 | 0.0430 | 557 | 1014 |
| Liberation Mono | bold_italic | Mama illu &%8 | 10 | 186.365 | 187.802 | +0.771 | 0.1463 | 570 | 1014 |
| Liberation Mono | bold_italic | Mama illu &%8 | 50 | 4680.695 | 4695.045 | +0.307 | 0.2160 | 694 | 1014 |
| Comfortaa | regular | SOLIDON3D | 3 | 11.330 | 11.363 | +0.288 | 0.0129 | 477 | 972 |
| Comfortaa | regular | SOLIDON3D | 10 | 125.889 | 126.249 | +0.287 | 0.0428 | 477 | 973 |
| Comfortaa | regular | SOLIDON3D | 50 | 3150.772 | 3156.284 | +0.175 | 0.2216 | 611 | 970 |
| Comfortaa | regular | Deckel 120 x 80 | 3 | 12.393 | 12.463 | +0.565 | 0.0143 | 615 | 1163 |
| Comfortaa | regular | Deckel 120 x 80 | 10 | 137.701 | 138.477 | +0.564 | 0.0475 | 615 | 1164 |
| Comfortaa | regular | Deckel 120 x 80 | 50 | 3450.835 | 3462.158 | +0.328 | 0.2349 | 769 | 1152 |
| Comfortaa | regular | Ölwanne Größe 12,5 mm | 3 | 19.115 | 19.189 | +0.387 | 0.0096 | 1106 | 1853 |
| Comfortaa | regular | Ölwanne Größe 12,5 mm | 10 | 212.386 | 213.203 | +0.385 | 0.0320 | 1106 | 1859 |
| Comfortaa | regular | Ölwanne Größe 12,5 mm | 50 | 5316.895 | 5330.167 | +0.250 | 0.1475 | 1349 | 1854 |
| Comfortaa | regular | AVATAR Toyota WAVE | 3 | 18.300 | 18.347 | +0.255 | 0.0096 | 614 | 902 |
| Comfortaa | regular | AVATAR Toyota WAVE | 10 | 203.336 | 203.847 | +0.251 | 0.0320 | 614 | 908 |
| Comfortaa | regular | AVATAR Toyota WAVE | 50 | 5088.882 | 5096.296 | +0.146 | 0.1718 | 740 | 904 |
| Comfortaa | regular | Mama illu &%8 | 3 | 12.892 | 12.940 | +0.368 | 0.0096 | 690 | 1124 |
| Comfortaa | regular | Mama illu &%8 | 10 | 143.249 | 143.771 | +0.364 | 0.0320 | 690 | 1128 |
| Comfortaa | regular | Mama illu &%8 | 50 | 3587.146 | 3594.373 | +0.201 | 0.1637 | 856 | 1126 |
| Dancing Script | regular | SOLIDON3D | 3 | 9.087 | 9.115 | +0.314 | 0.0085 | 887 | 1700 |
| Dancing Script | regular | SOLIDON3D | 10 | 100.966 | 101.286 | +0.317 | 0.0296 | 887 | 1703 |
| Dancing Script | regular | SOLIDON3D | 50 | 2527.760 | 2532.080 | +0.171 | 0.1388 | 1019 | 1701 |
| Dancing Script | regular | Deckel 120 x 80 | 3 | 8.872 | 8.912 | +0.449 | 0.0108 | 965 | 1767 |
| Dancing Script | regular | Deckel 120 x 80 | 10 | 98.577 | 99.020 | +0.449 | 0.0360 | 965 | 1764 |
| Dancing Script | regular | Deckel 120 x 80 | 50 | 2468.813 | 2475.435 | +0.268 | 0.2019 | 1103 | 1762 |
| Dancing Script | regular | Ölwanne Größe 12,5 mm | 3 | 11.160 | 11.210 | +0.447 | 0.0097 | 1656 | 2537 |
| Dancing Script | regular | Ölwanne Größe 12,5 mm | 10 | 123.998 | 124.552 | +0.446 | 0.0324 | 1656 | 2534 |
| Dancing Script | regular | Ölwanne Größe 12,5 mm | 50 | 3105.999 | 3113.795 | +0.251 | 0.1850 | 1817 | 2534 |
| Dancing Script | regular | AVATAR Toyota WAVE | 3 | 13.150 | 13.196 | +0.349 | 0.0102 | 1458 | 2624 |
| Dancing Script | regular | AVATAR Toyota WAVE | 10 | 146.114 | 146.626 | +0.350 | 0.0341 | 1458 | 2625 |
| Dancing Script | regular | AVATAR Toyota WAVE | 50 | 3657.906 | 3665.596 | +0.210 | 0.1833 | 1589 | 2623 |
| Dancing Script | regular | Mama illu &%8 | 3 | 8.048 | 8.081 | +0.407 | 0.0229 | 1059 | 1774 |
| Dancing Script | regular | Mama illu &%8 | 10 | 89.426 | 89.794 | +0.412 | 0.0762 | 1059 | 1778 |
| Dancing Script | regular | Mama illu &%8 | 50 | 2238.766 | 2244.712 | +0.266 | 0.2486 | 1169 | 1774 |

Größte Abweichung je Schrifthöhe (Hausdorff mm, |Δ Fläche| %):
- 3 mm: 0.0888 mm, 2.068 %
- 10 mm: 0.2266 mm, 0.591 %
- 50 mm: 0.2665 mm, 0.369 %

Exakter Körper „SOLIDON3D“, 10 mm, 1 mm hoch (Volumen mm³ alt / neu):
- DejaVu Sans regular: 143.1247 / 143.1345 (+0.007 %)
- DejaVu Sans bold: 245.4885 / 245.4972 (+0.004 %)
- DejaVu Sans italic: 142.3938 / 142.3733 (-0.014 %)
- DejaVu Sans bold_italic: 246.1770 / 246.1485 (-0.012 %)
- DejaVu Serif regular: 137.9822 / 137.9786 (-0.003 %)
- DejaVu Serif bold: 222.2759 / 222.2831 (+0.003 %)
- DejaVu Serif italic: 138.0451 / 137.9992 (-0.033 %)
- DejaVu Serif bold_italic: 222.2752 / 222.2731 (-0.001 %)
- DejaVu Sans Mono regular: 136.4791 / 136.4438 (-0.026 %)
- DejaVu Sans Mono bold: 189.6944 / 189.6629 (-0.017 %)
- DejaVu Sans Mono italic: 136.2459 / 136.2301 (-0.012 %)
- DejaVu Sans Mono bold_italic: 189.2947 / 189.2787 (-0.008 %)
- Liberation Sans regular: 128.9124 / 128.9087 (-0.003 %)
- Liberation Sans bold: 186.5583 / 186.5448 (-0.007 %)
- Liberation Sans italic: 126.7561 / 126.7324 (-0.019 %)
- Liberation Sans bold_italic: 183.5154 / 183.5026 (-0.007 %)
- Liberation Serif regular: 108.9580 / 108.9098 (-0.044 %)
- Liberation Serif bold: 157.3885 / 157.3568 (-0.020 %)
- Liberation Serif italic: 106.3695 / 106.3227 (-0.044 %)
- Liberation Serif bold_italic: 147.7071 / 147.6638 (-0.029 %)
- Liberation Mono regular: 120.9859 / 120.9527 (-0.027 %)
- Liberation Mono bold: 173.5559 / 173.5289 (-0.016 %)
- Liberation Mono italic: 120.9365 / 120.9102 (-0.022 %)
- Liberation Mono bold_italic: 173.2945 / 173.2781 (-0.009 %)
- Comfortaa regular: 126.3439 / 126.3561 (+0.010 %)
- Dancing Script regular: 101.4066 / 101.4035 (-0.003 %)

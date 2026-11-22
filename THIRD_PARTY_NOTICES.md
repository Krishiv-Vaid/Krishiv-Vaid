# Third-party notices

## JetBrains Mono

`fonts/JetBrainsMonoNL-*.ttf` are from [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono)
v2.304. Subsets of these fonts are embedded in the generated SVGs.
Licensed under the SIL Open Font License 1.1; see [`fonts/OFL.txt`](fonts/OFL.txt) and
[`fonts/AUTHORS.txt`](fonts/AUTHORS.txt).

## Git Tulkun

The evolving coin is an original Python implementation, inspired by
[Git Tulkun](https://github.com/PramudithaN/git-tulkun) by Pramuditha Nadun. No source
code was copied. The following ideas were adapted from its design and documentation:

- the concave growth curve `g = min(1, (contributions / 2800) ^ 0.45)`
  ([`profilegen/coin/evolution.py`](profilegen/coin/evolution.py));
- deriving a 4-step shade ramp from each GitHub language colour
  ([`profilegen/coin/palette.py`](profilegen/coin/palette.py));
- publishing generated assets to a separate `output` branch from a scheduled workflow.

Git Tulkun is distributed under the following license:

```
MIT License

Copyright (c) 2026 Pramuditha Nadun

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

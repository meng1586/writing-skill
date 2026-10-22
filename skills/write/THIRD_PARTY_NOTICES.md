# 第三方组件与许可

本包除下列文件外，方法摘要为本项目改写，不自动整体声明为 MIT。

## 检测脚本（原样复制）

| 文件 | 来源 | 提交 | 许可 | 改动 |
|---|---|---|---|---|
| `scripts/check-ai-patterns.js` | https://github.com/zenstory-ai/oh-story-claudecode | `7408014` | MIT | 原样复制，未改算法 |
| `scripts/check-degeneration.js` | 同上 | `7408014` | MIT | 原样复制 |
| `scripts/style-whitelist.js` | 同上 | `7408014` | MIT | 原样复制（前者的同目录依赖） |

完整许可：https://github.com/zenstory-ai/oh-story-claudecode/blob/7408014/LICENSE

```
MIT License

Copyright (c) 2025-2026 oh-story-claudecode

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

## 使用边界

- 三个脚本只作编辑线索；`--fail-on=blocking` 只用于生成/清理时的提示，命中不等于必须机械重写。
- 需要 Node（可选，无 npm 依赖）；`check-ai-patterns.js` 依赖同目录 `style-whitelist.js`。
- 算法与输出文案未改；本项目的调用方式见 `references/resources.md`。

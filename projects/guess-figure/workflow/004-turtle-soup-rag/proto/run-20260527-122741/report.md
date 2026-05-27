# 004 Turtle Soup RAG Prototype Report

- 运行时间：2026-05-27 12:27:41 +0800
- 结果：14/15 cases passed
- embedding：1024 维 deterministic mock（用于验证 Vectorize 维度契约，不代表真实语义质量）
- chunk：500-800 中文字，overlap 100

## Cloudflare 预检

- Workers AI 模型存在：已通过 wrangler ai models --json 验证 qwen3-embedding/bge-m3/reranker 存在
- Vectorize index：账号可访问 Vectorize，但尚未创建 index
- R2 状态：R2 尚未启用，wrangler r2 bucket list 返回 code 10042
- D1 状态：guess-figure-db 已存在

## Corpus

```json
{
  "targets": [
    {
      "figure": "诸葛亮",
      "aliases": [
        "孔明",
        "卧龙",
        "忠武侯",
        "诸葛武侯"
      ],
      "sources": [
        {
          "type": "profile",
          "ref": "src\\lib\\data\\profiles\\诸葛亮.md",
          "chars": 1063,
          "chunks": 2
        },
        {
          "type": "wikisource",
          "ref": "三國志/卷35",
          "chars": 6000,
          "chunks": 9
        }
      ]
    },
    {
      "figure": "关羽",
      "aliases": [
        "云长",
        "壮缪侯",
        "关公",
        "关帝",
        "关圣帝君"
      ],
      "sources": [
        {
          "type": "profile",
          "ref": "src\\lib\\data\\profiles\\关羽.md",
          "chars": 1106,
          "chunks": 2
        },
        {
          "type": "wikisource",
          "ref": "三國志/卷36",
          "chars": 4562,
          "chunks": 7
        }
      ]
    },
    {
      "figure": "苏轼",
      "aliases": [
        "子瞻",
        "东坡居士",
        "文忠",
        "苏文忠公",
        "苏仙"
      ],
      "sources": [
        {
          "type": "profile",
          "ref": "src\\lib\\data\\profiles\\苏轼.md",
          "chars": 954,
          "chunks": 2
        },
        {
          "type": "wikisource",
          "ref": "宋史/卷338",
          "chars": 6000,
          "chunks": 9
        }
      ]
    }
  ],
  "chunk_policy": {
    "min_chars": 500,
    "max_chars": 800,
    "overlap_chars": 100
  }
}
```

## Cases

| # | figure | question | expected | actual | pass | top evidence |
|---|---|---|---|---|---|---|
| 1 | 诸葛亮 | 他是不是蜀汉丞相？ | 是 | 是 | PASS | profile:src\lib\data\profiles\诸葛亮.md#0 |
| 2 | 诸葛亮 | 他是否写过出师表？ | 是 | 是 | PASS | profile:src\lib\data\profiles\诸葛亮.md#0 |
| 3 | 诸葛亮 | 他是不是唐朝诗人？ | 否 | 否 | PASS | profile:src\lib\data\profiles\诸葛亮.md#0 |
| 4 | 诸葛亮 | 他跟刘备有关吗？ | 是 | 是 | PASS | profile:src\lib\data\profiles\诸葛亮.md#0 |
| 5 | 诸葛亮 | 他是谁？ | invalid | invalid | PASS | n/a |
| 6 | 关羽 | 他是不是被后世尊为武圣？ | 是 | 无关 | FAIL | profile:src\lib\data\profiles\关羽.md#0 |
| 7 | 关羽 | 他是否跟刘备有关？ | 是 | 是 | PASS | profile:src\lib\data\profiles\诸葛亮.md#1 |
| 8 | 关羽 | 他是不是宋朝文人？ | 否 | 否 | PASS | profile:src\lib\data\profiles\关羽.md#0 |
| 9 | 关羽 | 他有没有在荆州失守相关事件中失败？ | 是 | 是 | PASS | profile:src\lib\data\profiles\关羽.md#0 |
| 10 | 关羽 | 介绍他的作品 | invalid | invalid | PASS | n/a |
| 11 | 苏轼 | 他是不是宋代文人？ | 是 | 是 | PASS | profile:src\lib\data\profiles\苏轼.md#0 |
| 12 | 苏轼 | 他是否写过赤壁赋？ | 是 | 是 | PASS | profile:src\lib\data\profiles\苏轼.md#0 |
| 13 | 苏轼 | 他是不是蜀汉丞相？ | 否 | 否 | PASS | profile:src\lib\data\profiles\苏轼.md#0 |
| 14 | 苏轼 | 他跟王安石变法有关吗？ | 是 | 是 | PASS | profile:src\lib\data\profiles\苏轼.md#0 |
| 15 | 苏轼 | 他有哪些作品？ | invalid | invalid | PASS | n/a |

## 结论

- RAG 查询必须把目标人物姓名/别名作为隐藏 query expansion 注入，否则用户问题中的「他」无法稳定召回。
- 全量语料链路需要 R2 启用和 Vectorize index 创建；当前账号可访问 Vectorize/Workers AI，但尚未创建 index，R2 尚未启用。
- mock embedding 只能验证接口形状；Stage 4 SPEC 应要求 Stage 7 用真实 Workers AI embedding + Vectorize 做集成测试。

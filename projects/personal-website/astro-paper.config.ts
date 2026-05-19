import { defineAstroPaperConfig } from "./src/types/config";

export default defineAstroPaperConfig({
  site: {
    url: "https://lw-personal.pages.dev/",
    title: "李旺 · 个人网站",
    description:
      "李旺的个人网站：后端开发者，业余在用 AI 辅助开发做点东西。含项目卡片与博客。",
    author: "李旺",
    profile: "https://github.com/znlm1229",
    ogImage: "default-og.jpg",
    lang: "zh-CN",
    timezone: "Asia/Shanghai",
    dir: "ltr",
  },
  posts: {
    perPage: 4,
    perIndex: 4,
    scheduledPostMargin: 15 * 60 * 1000,
  },
  features: {
    lightAndDarkMode: true,
    dynamicOgImage: true,
    showArchives: true,
    showBackButton: true,
    // MVP 不启用「edit on github」按钮（避免暴露仓库结构 / 简化首版）
    editPost: { enabled: false },
    search: "pagefind",
  },
  // 仅保留 GitHub —— 移除 starter 默认的 mailto:yourmail@gmail.com 等占位
  // mailto 留在 starter socials 里会违反 AC10（HTML 不含明文邮箱）
  // 邮件联系入口在首页 #contact 与 /about 通过 EmailLink 组件混淆呈现
  socials: [
    { name: "github", url: "https://github.com/znlm1229" },
  ],
  // 文章页"分享到..."按钮的目标（不含明文邮箱地址，是模板 URL，合规）
  shareLinks: [
    { name: "x",        url: "https://x.com/intent/post?url=" },
    { name: "telegram", url: "https://t.me/share/url?url=" },
    { name: "facebook", url: "https://www.facebook.com/sharer.php?u=" },
  ],
});

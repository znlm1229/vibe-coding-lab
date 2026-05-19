import { defineCollection } from "astro:content";
import { z } from "astro/zod";
import { glob } from "astro/loaders";
import config from "@/config";

export const BLOG_PATH = "src/content/posts";
export const PROJECTS_PATH = "src/content/projects";

const posts = defineCollection({
  loader: glob({ pattern: "**/[^_]*.{md,mdx}", base: `./${BLOG_PATH}` }),
  schema: ({ image }) =>
    z.object({
      author: z.string().default(config.site.author),
      pubDatetime: z.date(),
      modDatetime: z.date().optional().nullable(),
      title: z.string(),
      featured: z.boolean().optional(),
      draft: z.boolean().optional(),
      tags: z.array(z.string()).default(["others"]),
      ogImage: image().or(z.string()).optional(),
      description: z.string(),
      canonicalURL: z.string().optional(),
      hideEditPost: z.boolean().optional(),
      timezone: z.string().optional(),
    }),
});

const pages = defineCollection({
  loader: glob({ pattern: "**/[^_]*.{md,mdx}", base: "./src/content/pages" }),
  schema: z.object({
    title: z.string(),
    description: z.string().optional(),
    ogImage: z.string().optional(),
    canonicalURL: z.string().optional(),
  }),
});

// 项目卡集合：列表页 /projects 与详情页 /projects/<slug> 的数据源
const projects = defineCollection({
  loader: glob({
    pattern: "**/[^_]*.{md,mdx}",
    base: `./${PROJECTS_PATH}`,
  }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      summary: z.string(), // 卡片摘要，1-2 句
      tech: z.array(z.string()).default([]), // 技术栈 tag 列表
      githubUrl: z.string().url().optional(),
      liveUrl: z.string().url().optional(),
      screenshot: image().or(z.string()).optional(),
      // active = 在做或维护中；wip = 进行中（占位）；archived = 已归档
      status: z.enum(["active", "wip", "archived"]).default("active"),
      pubDate: z.date().optional(), // 上线/启动日期，用于排序
      featured: z.boolean().optional(), // 首页是否精选展示
      order: z.number().optional(), // 同等 featured 下的手动排序
      draft: z.boolean().optional(), // 草稿不出现在生产
    }),
});

export const collections = { posts, pages, projects };

// T14: 每日一题路由
//
// SPEC 决策 6: daily 按 UTC 16:00 切换 = 北京 0:00。
// SPEC 决策 4 / OQ4: 按入库顺序选题。
// SPEC OQ1: 题库耗尽（第 51 天起）进入"经典回顾"轮播。
//
// 输出: { figure_id, date, mode: "fresh" | "replay", day_index }

import { json } from "@sveltejs/kit";
import figures from "$lib/data/figures.json";
import type { Figure } from "$lib/types";
import type { RequestHandler } from "./$types";

// V1 上线锚定日（用作 day index 计算）。
// 选定：2026-05-21 = V1 题库 50 人全量入库 + 上线测试当日的北京 0:00 = UTC 2026-05-21 00:00。
// dayIndex=0 → figures[0]（按 id 字符串排序后首位）= V1 上线日的题。
// 注意：每日切换发生在 UTC 16:00 = 北京次日 00:00，所以 UTC 16:00 前 dailyDate 回退一天。
const LAUNCH_DATE_UTC = "2026-05-21"; // 必须是 UTC 日字符串

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * 当前的 daily "日"。
 *
 * 按 UTC 16:00 切换（= 北京 0:00）：
 * - UTC 时间 < 16:00 → 当前 daily 日是前一天的 UTC 日
 * - UTC 时间 >= 16:00 → 当前 daily 日是今天的 UTC 日
 *
 * 这样北京时间 0:00 之前都用同一题，0:00 后才换。
 */
function getCurrentDailyDate(now: Date): Date {
  const d = new Date(now);
  if (d.getUTCHours() < 16) {
    d.setUTCDate(d.getUTCDate() - 1);
  }
  // 归到 UTC 当日 00:00
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

function dateToYMD(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export const GET: RequestHandler = async () => {
  const list = figures as Figure[];
  if (!list.length) {
    return json({ error: "题库为空" }, { status: 500 });
  }

  const now = new Date();
  const dailyDate = getCurrentDailyDate(now);
  const launchDate = new Date(LAUNCH_DATE_UTC + "T00:00:00Z");

  const dayIndex = Math.floor((dailyDate.getTime() - launchDate.getTime()) / MS_PER_DAY);
  const safeIndex = ((dayIndex % list.length) + list.length) % list.length; // 防负数

  const figure = list[safeIndex];
  const mode: "fresh" | "replay" = dayIndex >= list.length ? "replay" : "fresh";

  return json({
    figure_id: figure.id,
    date: dateToYMD(dailyDate),
    day_index: dayIndex,
    mode,
  });
};

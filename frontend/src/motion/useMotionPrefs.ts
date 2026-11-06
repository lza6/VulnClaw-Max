import { useReducedMotion } from "motion/react";
import { EASE_STANDARD, EASE_EXIT, type Ease } from "./tokens";

export interface MotionPrefs {
  /** 系统开启了"减少动态效果" */
  reduce: boolean;
  /** 需要显式时长时用：reduce 下返回 0 */
  seconds: (seconds: number) => number;
  ease: Ease;
  exitEase: Ease;
}

/**
 * motion 的 inline transform 改不了媒体查询，所以 reduce 必须走这个入口：
 * 所有动画时长由此计算，reduce 时归零，等价于"立即到位"。
 */
export function useMotionPrefs(): MotionPrefs {
  const reduce = Boolean(useReducedMotion());
  return {
    reduce,
    seconds: (seconds) => (reduce ? 0 : seconds),
    ease: EASE_STANDARD,
    exitEase: EASE_EXIT,
  };
}

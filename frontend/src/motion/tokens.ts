/** 动效令牌：数值与 styles/tokens.css 的 --dur-* 一一对应，改一处必须改两处 */
export const DURATION = {
  /** 120ms：hover / press / 颜色过渡 */
  instant: 0.12,
  /** 180ms：组件进入退出 */
  fast: 0.18,
  /** 260ms：页面与分区切换 */
  base: 0.26,
  /** 420ms：首屏一次性叙事 */
  slow: 0.42,
} as const;

export type Ease = [number, number, number, number];

export const EASE_STANDARD: Ease = [0.2, 0, 0, 1];
export const EASE_EXIT: Ease = [0.4, 0, 1, 1];

/** 视图切换：淡入 + 8px 上移 */
export const VIEW_TRANSITION = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
};

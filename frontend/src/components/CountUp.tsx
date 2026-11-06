import { useEffect, useRef, useState } from "react";
import { useMotionPrefs } from "../motion/useMotionPrefs";
import { DURATION } from "../motion/tokens";

interface CountUpProps {
  value: number;
  suffix?: string;
}

/**
 * 数字从上一值滚到新值。用 rAF 自绘而不是 motion 的命令式 animate：
 * 只改文本，不参与 motion 特性包，省下几十 KB。
 * reduced-motion 下直接显示终值——数值是信息，动画只是过渡。
 */
export function CountUp({ value, suffix = "" }: CountUpProps) {
  const { reduce } = useMotionPrefs();
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const from = fromRef.current;
    if (reduce || from === value) {
      fromRef.current = value;
      setDisplay(value);
      return;
    }
    const duration = DURATION.slow * 1000;
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step);
      } else {
        fromRef.current = value;
        frameRef.current = null;
      }
    };
    frameRef.current = requestAnimationFrame(step);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
      fromRef.current = value;
    };
  }, [value, reduce]);

  return (
    <span data-count-up={value}>
      {display}
      {suffix}
    </span>
  );
}

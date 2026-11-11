export interface AttackSurfaceNode {
  id: string;
  label: string;
  /** 已归一化的严重度：Critical / High / Medium / Low / 其它 */
  severity: string;
}

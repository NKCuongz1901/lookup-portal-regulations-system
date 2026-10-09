import Link from "next/link";
import styles from "./Brand.module.scss";

export default function Brand({ light = false, href = "/dashboard" }: { light?: boolean; href?: string }) {
  return <Link href={href} className={`${styles.brand} ${light ? styles.light : ""}`} aria-label="Regula — Trang tổng quan">
    <svg width="38" height="40" viewBox="0 0 40 42" fill="none" aria-hidden="true">
      <path d="M20 2 39 11 20 20 1 11 20 2Z" fill="currentColor" />
      <path d="m1 20 8-4 11 5 11-5 8 4-19 9L1 20Z" fill="currentColor" opacity=".7" />
      <path d="m1 29 8-4 11 5 11-5 8 4-19 9L1 29Z" fill="currentColor" opacity=".4" />
    </svg><span>Regula<span className={styles.dot}>.</span></span>
  </Link>;
}

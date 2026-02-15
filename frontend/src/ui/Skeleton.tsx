import { useTheme } from "@/context/ThemeContext";

const pulseKeyframes = `
@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
`;

function Skeleton({ width, height, borderRadius = 8 }: { width?: string | number; height?: string | number; borderRadius?: number }) {
  const theme = useTheme();
  return (
    <>
      <style>{pulseKeyframes}</style>
      <div
        style={{
          width: width ?? "100%",
          height: height ?? 16,
          borderRadius,
          backgroundColor: theme.bgTertiary,
          animation: "skeleton-pulse 1.5s ease-in-out infinite",
        }}
      />
    </>
  );
}

function SkeletonCard() {
  const theme = useTheme();
  return (
    <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: "14px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
        <Skeleton width="60%" height={16} />
        <Skeleton width={60} height={16} borderRadius={6} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Skeleton width="40%" height={14} />
        <Skeleton width={80} height={14} />
      </div>
    </div>
  );
}

function SkeletonList({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingTop: 8 }}>
      <Skeleton width="40%" height={22} borderRadius={6} />
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

function SkeletonDetail() {
  const theme = useTheme();
  return (
    <div style={{ paddingTop: 8, paddingBottom: 16 }}>
      <Skeleton width={60} height={16} borderRadius={6} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 16, marginBottom: 16 }}>
        <Skeleton width="50%" height={24} />
        <Skeleton width={80} height={24} borderRadius={8} />
      </div>
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16, marginBottom: 16 }}>
        <Skeleton width="70%" height={18} />
        <div style={{ marginTop: 12 }}>
          <Skeleton width="100%" height={14} />
          <div style={{ marginTop: 8 }}><Skeleton width="80%" height={14} /></div>
          <div style={{ marginTop: 8 }}><Skeleton width="60%" height={14} /></div>
        </div>
      </div>
      <div style={{ backgroundColor: theme.bgSecondary, borderRadius: 14, padding: 16 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: `1px solid ${theme.border}` }}>
            <Skeleton width="35%" height={14} />
            <Skeleton width="30%" height={14} />
          </div>
        ))}
      </div>
    </div>
  );
}

export { Skeleton, SkeletonCard, SkeletonList, SkeletonDetail };
export default Skeleton;

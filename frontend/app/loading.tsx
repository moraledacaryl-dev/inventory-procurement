export default function Loading() {
  return <main className="route-loading" aria-busy="true" aria-label="Loading page">
    <aside
      className="loading-sidebar"
      aria-hidden="true"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 20,
        padding: "24px 18px",
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, paddingBottom: 20, borderBottom: "1px solid rgba(255,255,255,.09)" }}>
        <div style={{ width: 40, height: 40, borderRadius: 12, background: "rgba(255,255,255,.92)" }} />
        <div style={{ display: "grid", gap: 7, flex: 1 }}>
          <div style={{ width: 112, height: 12, borderRadius: 6, background: "rgba(255,255,255,.32)" }} />
          <div style={{ width: 84, height: 8, borderRadius: 5, background: "rgba(255,255,255,.16)" }} />
        </div>
      </div>

      {[3, 4, 3].map((count, groupIndex) => <div key={groupIndex} style={{ display: "grid", gap: 9 }}>
        <div style={{ width: 72, height: 7, marginLeft: 10, borderRadius: 5, background: "rgba(255,255,255,.13)" }} />
        {Array.from({ length: count }, (_, itemIndex) => <div
          key={itemIndex}
          style={{
            height: 38,
            borderRadius: 10,
            background: itemIndex === 0 && groupIndex === 0 ? "rgba(255,255,255,.12)" : "rgba(255,255,255,.055)",
          }}
        />)}
      </div>)}

      <div style={{ marginTop: "auto", height: 46, borderTop: "1px solid rgba(255,255,255,.09)", paddingTop: 14 }}>
        <div style={{ width: 126, height: 9, borderRadius: 5, background: "rgba(255,255,255,.13)" }} />
      </div>
    </aside>

    <div className="loading-main">
      <div className="loading-line loading-title" />
      <div className="loading-line loading-subtitle" />
      <div className="loading-grid"><div/><div/><div/></div>
      <div className="loading-panel" />
    </div>
  </main>;
}

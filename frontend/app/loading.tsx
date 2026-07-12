export default function Loading() {
  const skeleton = "linear-gradient(90deg,#e8ecea 25%,#f6f8f7 50%,#e8ecea 75%)";

  return <main className="route-loading" aria-busy="true" aria-label="Loading page">
    <aside
      aria-hidden="true"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 20,
        minHeight: "100vh",
        padding: "24px 18px",
        overflow: "hidden",
        background: "#f4f6f5",
        borderRight: "1px solid #e2e8e5",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, paddingBottom: 20, borderBottom: "1px solid #e2e8e5" }}>
        <div style={{ width: 40, height: 40, borderRadius: 12, background: skeleton, backgroundSize: "200% 100%" }} />
        <div style={{ display: "grid", gap: 7, flex: 1 }}>
          <div style={{ width: 112, height: 12, borderRadius: 6, background: skeleton, backgroundSize: "200% 100%" }} />
          <div style={{ width: 84, height: 8, borderRadius: 5, background: skeleton, backgroundSize: "200% 100%" }} />
        </div>
      </div>

      {[3, 4, 3].map((count, groupIndex) => <div key={groupIndex} style={{ display: "grid", gap: 9 }}>
        <div style={{ width: 72, height: 7, marginLeft: 10, borderRadius: 5, background: "#e4e9e6" }} />
        {Array.from({ length: count }, (_, itemIndex) => <div
          key={itemIndex}
          style={{
            height: 38,
            borderRadius: 10,
            background: itemIndex === 0 && groupIndex === 0 ? "#e8eeeb" : "#edf1ef",
            border: "1px solid #e2e8e5",
          }}
        />)}
      </div>)}

      <div style={{ marginTop: "auto", height: 46, borderTop: "1px solid #e2e8e5", paddingTop: 14 }}>
        <div style={{ width: 126, height: 9, borderRadius: 5, background: "#e4e9e6" }} />
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

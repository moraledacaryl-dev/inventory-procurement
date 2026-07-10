export default function Loading() {
  return <main className="route-loading" aria-busy="true" aria-label="Loading page">
    <div className="loading-sidebar" />
    <div className="loading-main">
      <div className="loading-line loading-title" />
      <div className="loading-line loading-subtitle" />
      <div className="loading-grid"><div/><div/><div/></div>
      <div className="loading-panel" />
    </div>
  </main>;
}

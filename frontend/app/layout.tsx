import "./globals.css";
import "./shell.css";
import "./dashboard.css";
import "./modules.css";
import "./ui-foundation.css";
import "./feedback.css";
import "./forms.css";
import "./auth.css";
import "./permissions.css";
import "./shell-completion.css";
import "./role-workspace.css";
import "./item-detail.css";
import "./catalogue-configuration.css";
import "./location-controls.css";
import "./stock-ledger.css";
import "./inventory-controls.css";
import "./guided-counts.css";
import "./supplier-360.css";
import "./procurement-planning.css";
import "./quotation-po-workspace.css";
import "./receiving-workspace.css";

export const metadata = {
  title: { default: "Hidden Oasis Operations", template: "%s | Hidden Oasis" },
  description: "Inventory, procurement, production, and connected operations for Hidden Oasis",
  applicationName: "Hidden Oasis Operations",
};

export const viewport = { themeColor: "#14293b", colorScheme: "light" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}

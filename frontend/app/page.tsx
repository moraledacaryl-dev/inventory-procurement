import {redirect} from "next/navigation";
export default function Home(){redirect(process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1"?"/training":"/dashboard")}

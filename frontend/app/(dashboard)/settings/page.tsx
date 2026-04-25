import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import PushNotificationSetup from "@/components/notifications/PushNotificationSetup"

export default function SettingsPage() {
    return (
        <div className="container mx-auto py-10 px-4 max-w-2xl">
            <div className="mb-8">
                <Link 
                    href="/dashboard/planner" 
                    className="flex items-center text-sm text-slate-500 hover:text-slate-800 transition-colors"
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to Planner
                </Link>
            </div>

            <h1 className="text-3xl font-bold mb-8">Settings</h1>

            <div className="space-y-10">
                <section>
                    <h2 className="text-xl font-semibold mb-4">Notifications</h2>
                    <p className="text-slate-500 mb-6 text-sm">
                        Configure how you receive updates and reminders from FlowDesk.
                    </p>
                    <PushNotificationSetup />
                </section>
            </div>
        </div>
    )
}

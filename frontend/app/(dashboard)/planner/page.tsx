"use client"

import { useEffect, useState } from "react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { getTasks, toggleTask, deleteTask, TaskOut, TaskScope } from "@/lib/tasks"
import TaskCard from "@/components/tasks/TaskCard"
import AddTaskDialog from "@/components/tasks/AddTaskDialog"
import EditTaskDialog from "@/components/tasks/EditTaskDialog"
import { useApi } from "@/hooks/useApi"
import { toast } from "sonner"
import { AlertCircle, RefreshCcw } from "lucide-react"
import { Button } from "@/components/ui/button"

// ─── Inline SVG clipboard icon ────────────────────────────────────────────────
function ClipboardIcon() {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 64 64"
            fill="none"
            className="w-20 h-20 mx-auto"
            aria-hidden="true"
        >
            <circle cx="32" cy="32" r="30" fill="#EEF2FF" />
            <rect x="20" y="18" width="24" height="30" rx="3" fill="#C7D2FE" />
            <rect x="24" y="14" width="16" height="6" rx="2" fill="#818CF8" />
            <line x1="25" y1="28" x2="39" y2="28" stroke="#6366F1" strokeWidth="2" strokeLinecap="round" />
            <line x1="25" y1="34" x2="39" y2="34" stroke="#6366F1" strokeWidth="2" strokeLinecap="round" />
            <line x1="25" y1="40" x2="34" y2="40" stroke="#6366F1" strokeWidth="2" strokeLinecap="round" />
        </svg>
    )
}

// ─── Scope label helper ────────────────────────────────────────────────────────
const scopeLabel: Record<TaskScope, string> = {
    [TaskScope.DAILY]: "today",
    [TaskScope.WEEKLY]: "this week",
    [TaskScope.MONTHLY]: "this month",
}

// ─── Empty State: zero tasks ──────────────────────────────────────────────────
function EmptyState({ scope, onCreated }: { scope: TaskScope; onCreated: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 gap-4 text-center px-4">
            <ClipboardIcon />
            <h2 className="text-lg font-semibold text-gray-800">
                No tasks for {scopeLabel[scope]}
            </h2>
            <p className="text-sm text-gray-500 max-w-xs">
                Add your first task to get started
            </p>
            <AddTaskDialog scope={scope} onCreated={onCreated} />
        </div>
    )
}

// ─── All Done State ────────────────────────────────────────────────────────────
function AllDoneState({ count }: { count: number }) {
    return (
        <div className="flex flex-col items-center justify-center py-16 gap-3 text-center px-4">
            <div className="text-5xl select-none">🎉</div>
            <h2 className="text-lg font-semibold text-gray-800">All done!</h2>
            <p className="text-sm text-gray-500">
                You completed {count} task{count !== 1 ? "s" : ""}
            </p>
        </div>
    )
}

// ─── Error State ──────────────────────────────────────────────────────────────
function ErrorState({ scope, onRetry }: { scope: TaskScope; onRetry: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center py-12 gap-4 text-center px-4 border-2 border-dashed border-red-100 rounded-2xl bg-red-50/30">
            <div className="p-3 bg-red-100 rounded-full">
                <AlertCircle className="w-6 h-6 text-red-600" />
            </div>
            <div className="space-y-1">
                <h3 className="font-semibold text-gray-900">Could not load tasks</h3>
                <p className="text-sm text-gray-500">
                    There was a problem reaching the server for {scopeLabel[scope]}.
                </p>
            </div>
            <Button 
                variant="outline" 
                size="sm" 
                onClick={onRetry}
                className="gap-2 border-red-200 hover:bg-red-50 text-red-700"
            >
                <RefreshCcw className="w-4 h-4" />
                Tap to retry
            </Button>
        </div>
    )
}

// ─── Loading skeleton ──────────────────────────────────────────────────────────
function LoadingSkeleton() {
    return (
        <div className="space-y-3 animate-pulse">
            {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-xl bg-gray-100" />
            ))}
        </div>
    )
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function PlannerPage() {
    const { api } = useApi()
    const [tasks, setTasks] = useState<Record<TaskScope, TaskOut[]>>({
        DAILY: [],
        WEEKLY: [],
        MONTHLY: [],
    })

    const [loading, setLoading] = useState<Record<TaskScope, boolean>>({
        DAILY: true,
        WEEKLY: true,
        MONTHLY: true,
    })

    const [errors, setErrors] = useState<Record<TaskScope, boolean>>({
        DAILY: false,
        WEEKLY: false,
        MONTHLY: false,
    })

    const [activeTab, setActiveTab] = useState<TaskScope | "HISTORY">(TaskScope.DAILY)
    const [history, setHistory] = useState<TaskOut[]>([])
    const [historyLoading, setHistoryLoading] = useState(false)
    const [editingTask, setEditingTask] = useState<TaskOut | null>(null)

    const fetchTasks = async (scope: TaskScope) => {
        setLoading((prev) => ({ ...prev, [scope]: true }))
        setErrors((prev) => ({ ...prev, [scope]: false }))
        try {
            const authenticatedApi = await api()
            const res = await authenticatedApi.get<TaskOut[]>("/tasks", {
                params: { scope }
            })
            setTasks((prev) => ({ ...prev, [scope]: res.data }))
        } catch {
            setErrors((prev) => ({ ...prev, [scope]: true }))
            toast.error("Failed to load tasks")
        } finally {
            setLoading((prev) => ({ ...prev, [scope]: false }))
        }
    }

    const fetchHistory = async () => {
        setHistoryLoading(true)
        try {
            const authenticatedApi = await api()
            const res = await authenticatedApi.get<TaskOut[]>("/tasks", {
                params: { is_history: true }
            })
            setHistory(res.data)
        } catch {
            toast.error("Failed to load history")
        } finally {
            setHistoryLoading(false)
        }
    }

    useEffect(() => {
        fetchTasks(TaskScope.DAILY)
        fetchTasks(TaskScope.WEEKLY)
        fetchTasks(TaskScope.MONTHLY)
        fetchHistory()
    }, [])

    const handleToggle = async (task: TaskOut, scope: TaskScope | "HISTORY") => {
        const newState = !task.is_done
        
        if (scope === "HISTORY") {
            setHistory((prev) => prev.map(t => t.id === task.id ? { ...t, is_done: newState } : t))
        } else {
            setTasks((prev) => ({
                ...prev,
                [scope]: prev[scope].map((t) =>
                    t.id === task.id ? { ...t, is_done: newState } : t
                ),
            }))
        }

        try {
            await toggleTask(task.id, newState)
            if (newState) {
                // If marked as done, refresh history
                fetchHistory()
            }
        } catch {
            toast.error("Error toggling task")
            if (scope !== "HISTORY") await fetchTasks(scope)
            fetchHistory()
        }
    }

    const handleDelete = async (id: string, scope: TaskScope | "HISTORY") => {
        try {
            await deleteTask(id)
            if (scope === "HISTORY") {
                setHistory(prev => prev.filter(t => t.id !== id))
            } else {
                setTasks((prev) => ({
                    ...prev,
                    [scope]: prev[scope].filter((t) => t.id !== id),
                }))
            }
        } catch {
            toast.error("Delete failed")
        }
    }

    const renderTasks = (scope: TaskScope) => {
        if (loading[scope]) return <LoadingSkeleton />
        if (errors[scope]) return <ErrorState scope={scope} onRetry={() => fetchTasks(scope)} />

        const allTasks = tasks[scope]
        const undone = allTasks.filter((t) => !t.is_done)
        const done = allTasks.filter((t) => t.is_done)

        // Case 1: zero tasks at all
        if (allTasks.length === 0) {
            return <EmptyState scope={scope} onCreated={() => fetchTasks(scope)} />
        }

        // Case 2: all tasks are completed
        if (undone.length === 0) {
            return (
                <>
                    <AllDoneState count={done.length} />
                    <div className="space-y-3 opacity-60">
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-400 px-1">
                            Completed Today
                        </p>
                        {done.map((task) => (
                            <TaskCard
                                key={task.id}
                                task={task}
                                onToggle={(t) => handleToggle(t, scope)}
                                onDelete={(id) => handleDelete(id, scope)}
                                onEdit={setEditingTask}
                            />
                        ))}
                    </div>
                </>
            )
        }

        // Case 3: normal mix of done / undone
        return (
            <div className="space-y-3">
                {undone.map((task) => (
                    <TaskCard
                        key={task.id}
                        task={task}
                        onToggle={(t) => handleToggle(t, scope)}
                        onDelete={(id) => handleDelete(id, scope)}
                        onEdit={setEditingTask}
                    />
                ))}

                {done.length > 0 && (
                    <>
                        <div className="flex items-center gap-2 pt-2">
                            <hr className="flex-1 border-gray-200" />
                            <span className="text-xs text-gray-400 whitespace-nowrap">
                                {done.length} completed today
                            </span>
                            <hr className="flex-1 border-gray-200" />
                        </div>
                        <div className="space-y-3 opacity-70">
                            {done.map((task) => (
                                <TaskCard
                                    key={task.id}
                                    task={task}
                                    onToggle={(t) => handleToggle(t, scope)}
                                    onDelete={(id) => handleDelete(id, scope)}
                                    onEdit={setEditingTask}
                                />
                            ))}
                        </div>
                    </>
                )}
            </div>
        )
    }

    const renderHistory = () => {
        if (historyLoading) return <LoadingSkeleton />
        if (history.length === 0) {
            return (
                <div className="text-center py-12 bg-gray-50 rounded-2xl border-2 border-dashed border-gray-200">
                    <p className="text-gray-500">No completed tasks yet. Finish something!</p>
                </div>
            )
        }

        return (
            <div className="space-y-6">
                <div className="space-y-3">
                    {history.map((task) => (
                        <TaskCard
                            key={task.id}
                            task={task}
                            onToggle={(t) => handleToggle(t, "HISTORY")}
                            onDelete={(id) => handleDelete(id, "HISTORY")}
                            onEdit={setEditingTask}
                        />
                    ))}
                </div>
            </div>
        )
    }

    return (
        <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-2xl mx-auto">
            <Tabs
                defaultValue={TaskScope.DAILY}
                onValueChange={(v) => setActiveTab(v as any)}
            >
                {/* Header row — stacks vertically on mobile */}
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <TabsList className="w-full sm:w-auto">
                        <TabsTrigger value={TaskScope.DAILY} className="flex-1 sm:flex-none">
                            Today
                        </TabsTrigger>
                        <TabsTrigger value={TaskScope.WEEKLY} className="flex-1 sm:flex-none">
                            Week
                        </TabsTrigger>
                        <TabsTrigger value={TaskScope.MONTHLY} className="flex-1 sm:flex-none">
                            Month
                        </TabsTrigger>
                        <TabsTrigger value="HISTORY" className="flex-1 sm:flex-none">
                            History
                        </TabsTrigger>
                    </TabsList>

                    {/* Add Task button scoped to the currently active tab */}
                    {activeTab !== "HISTORY" && (
                        <div className="sm:ml-auto">
                            <AddTaskDialog
                                scope={activeTab as TaskScope}
                                onCreated={() => fetchTasks(activeTab as TaskScope)}
                            />
                        </div>
                    )}
                </div>

                <TabsContent value={TaskScope.DAILY}>{renderTasks(TaskScope.DAILY)}</TabsContent>
                <TabsContent value={TaskScope.WEEKLY}>{renderTasks(TaskScope.WEEKLY)}</TabsContent>
                <TabsContent value={TaskScope.MONTHLY}>{renderTasks(TaskScope.MONTHLY)}</TabsContent>
                <TabsContent value="HISTORY">{renderHistory()}</TabsContent>
            </Tabs>

            {/* Edit Task Dialog */}
            <EditTaskDialog
                task={editingTask}
                onClose={() => setEditingTask(null)}
                onUpdated={() => {
                    if (editingTask) {
                        if (activeTab === "HISTORY") fetchHistory()
                        else fetchTasks(editingTask.scope)
                    }
                }}
            />
        </div>
    )
}
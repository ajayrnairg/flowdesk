"use client"

import { useEffect, useState } from "react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { getTasks, toggleTask, deleteTask, TaskOut, TaskScope } from "@/lib/tasks"
import TaskCard from "@/components/tasks/TaskCard"
import AddTaskDialog from "@/components/tasks/AddTaskDialog"
import { toast } from "sonner"

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

    const [activeTab, setActiveTab] = useState<TaskScope>(TaskScope.DAILY)

    const fetchTasks = async (scope: TaskScope) => {
        setLoading((prev) => ({ ...prev, [scope]: true }))
        try {
            const data = await getTasks(scope)
            setTasks((prev) => ({ ...prev, [scope]: data }))
        } catch {
            toast.error("Failed to load tasks")
        } finally {
            setLoading((prev) => ({ ...prev, [scope]: false }))
        }
    }

    useEffect(() => {
        Promise.all([
            fetchTasks(TaskScope.DAILY),
            fetchTasks(TaskScope.WEEKLY),
            fetchTasks(TaskScope.MONTHLY),
        ]).catch(console.error)
    }, [])

    const handleToggle = async (task: TaskOut, scope: TaskScope) => {
        const newState = !task.is_done
        setTasks((prev) => ({
            ...prev,
            [scope]: prev[scope].map((t) =>
                t.id === task.id ? { ...t, is_done: newState } : t
            ),
        }))
        try {
            await toggleTask(task.id, newState)
        } catch {
            toast.error("Error toggling task")
            await fetchTasks(scope)
        }
    }

    const handleDelete = async (id: string, scope: TaskScope) => {
        try {
            await deleteTask(id)
            setTasks((prev) => ({
                ...prev,
                [scope]: prev[scope].filter((t) => t.id !== id),
            }))
        } catch {
            toast.error("Delete failed")
        }
    }

    const renderTasks = (scope: TaskScope) => {
        if (loading[scope]) return <LoadingSkeleton />

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
                            Completed
                        </p>
                        {done.map((task) => (
                            <TaskCard
                                key={task.id}
                                task={task}
                                onToggle={(t) => handleToggle(t, scope)}
                                onDelete={(id) => handleDelete(id, scope)}
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
                    />
                ))}

                {done.length > 0 && (
                    <>
                        <div className="flex items-center gap-2 pt-2">
                            <hr className="flex-1 border-gray-200" />
                            <span className="text-xs text-gray-400 whitespace-nowrap">
                                {done.length} completed
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
                                />
                            ))}
                        </div>
                    </>
                )}
            </div>
        )
    }

    return (
        <div className="p-4 sm:p-6 space-y-4 sm:space-y-6 max-w-2xl mx-auto">
            <Tabs
                defaultValue={TaskScope.DAILY}
                onValueChange={(v) => setActiveTab(v as TaskScope)}
            >
                {/* Header row — stacks vertically on mobile */}
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <TabsList className="w-full sm:w-auto">
                        <TabsTrigger value={TaskScope.DAILY} className="flex-1 sm:flex-none">
                            Today
                        </TabsTrigger>
                        <TabsTrigger value={TaskScope.WEEKLY} className="flex-1 sm:flex-none">
                            This Week
                        </TabsTrigger>
                        <TabsTrigger value={TaskScope.MONTHLY} className="flex-1 sm:flex-none">
                            This Month
                        </TabsTrigger>
                    </TabsList>

                    {/* Add Task button scoped to the currently active tab */}
                    <div className="sm:ml-auto">
                        <AddTaskDialog
                            scope={activeTab}
                            onCreated={() => fetchTasks(activeTab)}
                        />
                    </div>
                </div>

                <TabsContent value={TaskScope.DAILY}>{renderTasks(TaskScope.DAILY)}</TabsContent>
                <TabsContent value={TaskScope.WEEKLY}>{renderTasks(TaskScope.WEEKLY)}</TabsContent>
                <TabsContent value={TaskScope.MONTHLY}>{renderTasks(TaskScope.MONTHLY)}</TabsContent>
            </Tabs>
        </div>
    )
}
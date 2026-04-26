"use client"

import { TaskOut } from "@/lib/tasks"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { Trash2, Edit, RefreshCcw } from "lucide-react"

interface Props {
    task: TaskOut
    onToggle: (task: TaskOut) => void
    onDelete: (id: string) => void
    onEdit?: (task: TaskOut) => void // We will use this next
}

function isOverdue(dueDate: string | null) {
    if (!dueDate) return false
    const due = new Date(dueDate)
    const today = new Date()
    today.setHours(0, 0, 0, 0) // Compare dates only
    return due < today
}

export default function TaskCard({ task, onToggle, onDelete, onEdit }: Props) {
    const priorityColor = {
        HIGH: "bg-red-500",
        MEDIUM: "bg-yellow-500",
        LOW: "bg-green-500",
    }

    const overdue = isOverdue(task.due_date) && !task.is_done

    return (
        <div
            className={`flex items-center justify-between p-4 rounded-xl border bg-white shadow-sm transition-all ${
                task.is_done ? "opacity-50" : ""
            } ${overdue ? "border-red-300 bg-red-50/50" : ""}`}
        >
            <div className="flex items-center gap-3">
                <Checkbox
                    checked={task.is_done}
                    onCheckedChange={() => onToggle(task)}
                />

                <div>
                    <div className="flex items-center gap-2">
                        <p
                            className={`font-medium ${
                                task.is_done ? "line-through" : ""
                            }`}
                        >
                            {task.title}
                        </p>
                        {overdue && (
                            <p className="text-[10px] uppercase font-bold text-red-500 tracking-wider">
                                Overdue
                            </p>
                        )}
                        {task.parent_id && (
                            <RefreshCcw className="w-3 h-3 text-blue-400" />
                        )}
                    </div>
                    <p className={`text-sm ${overdue ? "text-red-500/80 font-medium" : "text-gray-500"}`}>
                        Due: {task.due_date || "No date"}
                    </p>
                </div>
            </div>

            <div className="flex items-center gap-1 sm:gap-3">
                {/* Priority badge */}
                <span
                    className={`text-xs text-white px-2 py-1 rounded hidden sm:inline-block ${priorityColor[task.priority]}`}
                >
                    {task.priority}
                </span>

                {/* Edit */}
                {onEdit && (
                    <Button variant="ghost" size="icon" onClick={() => onEdit(task)}>
                        <Edit className="w-4 h-4 text-blue-500" />
                    </Button>
                )}

                {/* Delete */}
                <Popover>
                    <PopoverTrigger asChild>
                        <Button variant="ghost" size="icon">
                            <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-40">
                        <p className="text-sm mb-2">Delete task?</p>
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => onDelete(task.id)}
                            className="w-full"
                        >
                            Confirm
                        </Button>
                    </PopoverContent>
                </Popover>
            </div>
        </div>
    )
}
"use client"

import { TaskOut } from "@/lib/tasks"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { Trash2 } from "lucide-react"

interface Props {
    task: TaskOut
    onToggle: (task: TaskOut) => void
    onDelete: (id: string) => void
}

export default function TaskCard({ task, onToggle, onDelete }: Props) {
    const priorityColor = {
        HIGH: "bg-red-500",
        MEDIUM: "bg-yellow-500",
        LOW: "bg-green-500",
    }

    return (
        <div
            className={`flex items-center justify-between p-4 rounded-xl border bg-white shadow-sm ${task.is_done ? "opacity-50" : ""
                }`}
        >
            <div className="flex items-center gap-3">
                <Checkbox
                    checked={task.is_done}
                    onCheckedChange={() => onToggle(task)}
                />

                <div>
                    <p
                        className={`font-medium ${task.is_done ? "line-through" : ""
                            }`}
                    >
                        {task.title}
                    </p>
                    <p className="text-sm text-gray-500">
                        Due: {task.due_date}
                    </p>
                </div>
            </div>

            <div className="flex items-center gap-3">
                {/* Priority badge */}
                <span
                    className={`text-xs text-white px-2 py-1 rounded ${priorityColor[task.priority]}`}
                >
                    {task.priority}
                </span>

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
                        >
                            Confirm
                        </Button>
                    </PopoverContent>
                </Popover>
            </div>
        </div>
    )
}
"use client"

import { useState } from "react"
import { createTask, TaskPriority, TaskScope } from "@/lib/tasks"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Calendar } from "@/components/ui/calendar"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { toast } from "sonner"

interface Props {
    scope: TaskScope
    onCreated: () => void
}

export default function AddTaskDialog({ scope, onCreated }: Props) {
    const [open, setOpen] = useState(false)
    const [title, setTitle] = useState("")
    const [notes, setNotes] = useState("")
    const [priority, setPriority] = useState<TaskPriority>(
        TaskPriority.MEDIUM
    )
    const [date, setDate] = useState<Date | undefined>(new Date())
    const [error, setError] = useState("")

    const handleSubmit = async () => {
        if (!title.trim()) {
            setError("Title is required")
            return
        }

        try {
            await createTask({
                title,
                notes,
                scope,
                priority,
                due_date: date ? date.toISOString().split("T")[0] : null,
            })

            setOpen(false)
            setTitle("")
            setNotes("")
            setError("")
            onCreated()
        } catch {
            toast.error("Failed to create task")
        }
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button>Add Task</Button>
            </DialogTrigger>

            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Add Task</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    <Input
                        placeholder="Title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                    />
                    {error && <p className="text-sm text-red-500">{error}</p>}

                    <Textarea
                        placeholder="Notes"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                    />

                    <Select
                        value={priority}
                        onValueChange={(v: any) => setPriority(v)}
                    >
                        <SelectTrigger>
                            <SelectValue placeholder="Priority" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="LOW">Low</SelectItem>
                            <SelectItem value="MEDIUM">Medium</SelectItem>
                            <SelectItem value="HIGH">High</SelectItem>
                        </SelectContent>
                    </Select>

                    <Calendar mode="single" selected={date} onSelect={setDate} />

                    <Button onClick={handleSubmit}>Create</Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}
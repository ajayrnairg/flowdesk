"use client"

import { useState, useEffect } from "react"
import { TaskOut, TaskPriority, updateTask } from "@/lib/tasks"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Calendar } from "@/components/ui/calendar"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { toast } from "sonner"

interface Props {
    task: TaskOut | null
    onClose: () => void
    onUpdated: () => void
}

export default function EditTaskDialog({ task, onClose, onUpdated }: Props) {
    const [title, setTitle] = useState("")
    const [notes, setNotes] = useState("")
    const [priority, setPriority] = useState<TaskPriority>(TaskPriority.MEDIUM)
    const [date, setDate] = useState<Date | undefined>(undefined)
    const [isRecurring, setIsRecurring] = useState(false)
    const [error, setError] = useState("")

    useEffect(() => {
        if (task) {
            setTitle(task.title)
            setNotes(task.notes || "")
            setPriority(task.priority)
            setIsRecurring(task.is_recurring)
            
            if (task.due_date) {
                const parts = task.due_date.split("-")
                if (parts.length === 3) {
                    setDate(new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2])))
                } else {
                    setDate(new Date(task.due_date))
                }
            } else {
                setDate(undefined)
            }
        }
    }, [task])

    const handleSubmit = async () => {
        if (!task) return
        if (!title.trim()) {
            setError("Title is required")
            return
        }

        try {
            await updateTask(task.id, {
                title,
                notes,
                priority,
                due_date: date ? date.toISOString().split("T")[0] : null,
                is_recurring: isRecurring,
            })

            setError("")
            onUpdated()
            onClose()
        } catch {
            toast.error("Failed to update task")
        }
    }

    if (!task) return null

    return (
        <Dialog open={!!task} onOpenChange={(open) => !open && onClose()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Edit Task</DialogTitle>
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

                    <div className="flex items-center space-x-2">
                        <Checkbox 
                            id="edit-recurring" 
                            checked={isRecurring} 
                            onCheckedChange={(checked) => setIsRecurring(!!checked)}
                        />
                        <Label htmlFor="edit-recurring">Recurring</Label>
                    </div>

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

                    <Button onClick={handleSubmit} className="w-full">Save Changes</Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}

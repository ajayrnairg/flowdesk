import api from "./api"
import { TaskScope, TaskPriority, TaskOut, TaskCreate, TaskUpdate } from "@/types/task"

export { TaskScope, TaskPriority }
export type { TaskOut, TaskCreate, TaskUpdate }

// Fetch tasks
export async function getTasks(scope?: TaskScope, isDone?: boolean) {
    const res = await api.get<TaskOut[]>("/tasks", {
        params: {
            scope,
            is_done: isDone,
        },
    })
    return res.data
}

// Create task
export async function createTask(data: TaskCreate) {
    const res = await api.post<TaskOut>("/tasks", data)
    return res.data
}

// Update task
export async function updateTask(
    id: string,
    data: TaskUpdate
) {
    const res = await api.patch<TaskOut>(`/tasks/${id}`, data)
    return res.data
}

// Toggle task
export async function toggleTask(id: string, is_done: boolean) {
    const res = await api.patch<TaskOut>(`/tasks/${id}/toggle`, { is_done })
    return res.data
}

// Delete task
export async function deleteTask(id: string) {
    await api.delete(`/tasks/${id}`)
}
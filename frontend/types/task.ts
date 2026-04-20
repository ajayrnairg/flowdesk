export enum TaskScope {
    DAILY = "DAILY",
    WEEKLY = "WEEKLY",
    MONTHLY = "MONTHLY",
}

export enum TaskPriority {
    LOW = "LOW",
    MEDIUM = "MEDIUM",
    HIGH = "HIGH",
}

export interface TaskCreate {
    title: string
    notes?: string | null
    priority?: TaskPriority
    due_date?: string | null
    scope: TaskScope
}

export interface TaskUpdate {
    title?: string
    notes?: string | null
    priority?: TaskPriority
    due_date?: string | null
}

export interface TaskOut {
    id: string
    user_id: string
    title: string
    notes: string | null
    scope: TaskScope
    priority: TaskPriority
    due_date: string | null
    is_done: boolean
    created_at: string
    updated_at: string
}

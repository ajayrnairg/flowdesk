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
    is_recurring?: boolean
}

export interface TaskUpdate {
    title?: string
    notes?: string | null
    priority?: TaskPriority
    due_date?: string | null
    is_recurring?: boolean
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
    is_recurring: boolean
    parent_id: string | null
    last_completed_at: string | null
    created_at: string
    updated_at: string
}

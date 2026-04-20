"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import Link from "next/link"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"

import api from "@/lib/api"
import { saveToken } from "@/lib/auth"

const schema = z.object({
    email: z.string().email(),
    password: z.string().min(6),
})

type LoginFormValues = z.infer<typeof schema>

export default function LoginPage() {
    const router = useRouter()
    const [error, setError] = useState("")

    const {
        register,
        handleSubmit,
        formState: { errors, isSubmitting },
    } = useForm<LoginFormValues>({
        resolver: zodResolver(schema),
    })

    const onSubmit = async (data: LoginFormValues) => {
        setError("")
        try {
            const res = await api.post("/auth/login", data)
            saveToken(res.data.access_token)
            router.push("/dashboard/planner")
        } catch (err: unknown) {
            const message = (err as Record<string, any>).response?.data?.message || "Login failed"
            setError(message)
        }
    }

    return (
        <div className="flex items-center justify-center min-h-screen">
            <Card className="w-full max-w-md">
                <CardHeader>
                    <CardTitle>Login to FlowDesk</CardTitle>
                </CardHeader>

                <CardContent>
                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input id="email" placeholder="m@example.com" {...register("email")} />
                            {errors.email && (
                                <p className="text-sm text-red-500">{errors.email.message}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="password">Password</Label>
                            <Input
                                id="password"
                                type="password"
                                placeholder="********"
                                {...register("password")}
                            />
                            {errors.password && (
                                <p className="text-sm text-red-500">
                                    {errors.password.message}
                                </p>
                            )}
                        </div>

                        {error && <p className="text-sm text-red-500">{error}</p>}

                        <Button className="w-full" disabled={isSubmitting}>
                            {isSubmitting ? "Logging in..." : "Login"}
                        </Button>
                    </form>

                    <p className="mt-4 text-sm text-center">
                        Don’t have an account?{" "}
                        <Link href="/register" className="text-blue-600 underline">
                            Register
                        </Link>
                    </p>
                </CardContent>
            </Card>
        </div>
    )
}
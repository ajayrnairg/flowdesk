"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

import api from "@/lib/api"

const schema = z.object({
    email: z.string().email(),
    password: z.string().min(6),
})

type FormData = z.infer<typeof schema>

export default function RegisterPage() {
    const router = useRouter()
    const [error, setError] = useState("")
    const [success, setSuccess] = useState("")

    const {
        register,
        handleSubmit,
        formState: { errors, isSubmitting },
    } = useForm<FormData>({
        resolver: zodResolver(schema),
    })

    const onSubmit = async (data: FormData) => {
        setError("")
        setSuccess("")
        try {
            await api.post("/auth/register", data)
            setSuccess("Account created successfully! Redirecting...")
            setTimeout(() => router.push("/login"), 1500)
        } catch (err: any) {
            setError(err.response?.data?.message || "Registration failed")
        }
    }

    return (
        <div className="flex items-center justify-center min-h-screen">
            <Card className="w-full max-w-md">
                <CardHeader>
                    <CardTitle>Create Account</CardTitle>
                </CardHeader>

                <CardContent>
                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        <div>
                            <Input placeholder="Email" {...register("email")} />
                            {errors.email && (
                                <p className="text-sm text-red-500">{errors.email.message}</p>
                            )}
                        </div>

                        <div>
                            <Input
                                type="password"
                                placeholder="Password"
                                {...register("password")}
                            />
                            {errors.password && (
                                <p className="text-sm text-red-500">
                                    {errors.password.message}
                                </p>
                            )}
                        </div>

                        {error && <p className="text-red-500 text-sm">{error}</p>}
                        {success && <p className="text-green-600 text-sm">{success}</p>}

                        <Button className="w-full" disabled={isSubmitting}>
                            {isSubmitting ? "Creating..." : "Register"}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    )
}
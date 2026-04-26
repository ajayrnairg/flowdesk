"use client"

import { SignUp } from "@clerk/nextjs"

/**
 * Same catch-all logic as sign-in route
 */
export default function Page() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <SignUp />
    </div>
  )
}

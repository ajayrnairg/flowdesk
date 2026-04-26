"use client"

import { SignIn } from "@clerk/nextjs"

/**
 * [[...sign-in]] is a catch-all route required by Clerk
 * It allows Clerk to handle internal routing like:
 * /sign-in, /sign-in/verify, /sign-in/sso-callback, etc.
 */
export default function Page() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <SignIn />
    </div>
  )
}

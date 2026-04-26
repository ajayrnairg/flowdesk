// Server-side usage
import { auth } from "@clerk/nextjs/server"

// Get token in server components / route handlers
export async function getClerkToken(): Promise<string | null> {
  const { getToken } = await auth()
  return await getToken()
}

/**
 * Client-side usage:
 * Use useAuth() from @clerk/nextjs inside components
 *
 * Example:
 * const { getToken } = useAuth()
 * const token = await getToken()
 */
import axios from "axios"


// Axios instance
const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL,
})

// Attach token manually when calling from a hook or component
// api.defaults.headers.common["Authorization"] will be set by useApi hook

// Handle 401 globally
api.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err.response?.status === 401) {
            if (typeof window !== "undefined" && (window as any).Clerk) {
                // If unauthorized, let Clerk handle it or redirect to sign-in
                const clerk = (window as any).Clerk;
                if (!clerk.user) {
                    clerk.redirectToSignIn();
                }
            }
        }
        return Promise.reject(err)
    }
)

export default api
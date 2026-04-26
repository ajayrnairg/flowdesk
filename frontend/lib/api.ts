import axios from "axios"


// Axios instance
const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL,
})

// Attach Clerk token via global Clerk object
api.interceptors.request.use(async (config) => {
    if (typeof window !== "undefined" && (window as any).Clerk) {
        try {
            const session = (window as any).Clerk.session;
            if (session) {
                const token = await session.getToken();
                if (token) {
                    config.headers.Authorization = `Bearer ${token}`;
                }
            }
        } catch (err) {
            console.error("Failed to get Clerk token", err);
        }
    }
    return config;
});

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
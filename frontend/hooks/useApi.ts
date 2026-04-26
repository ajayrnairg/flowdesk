import { useAuth } from "@clerk/nextjs";
import api from "@/lib/api";

export function useApi() {
  const { getToken } = useAuth();

  const authenticatedApi = async () => {
    const token = await getToken({ template: "flowdesk" });
    
    // Create a configured instance or just set the header on the existing one
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common["Authorization"];
    }
    
    return api;
  };

  return { api: authenticatedApi };
}

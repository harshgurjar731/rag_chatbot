import { API_BASE_URL } from "@/constants";
import { useEffect, useState } from "react"

export interface ConfigOptions {
  base_url: string
  optimizer: { value: string; label: string }[]
  embedding_models: string[]
  llm_providers: string[]
  llm_models: string[]
  vector_dbs: string[]
  reranker_options: string[]
  guardrail_options: { value: string; label: string }[]   // ✅ updated type
  default_temperature: number
  token_size_options:{ default: number; min: number; max: number; step: number }
  show_sources_default: boolean
  languages: { code: string; name: string }[] ,
  eval_framworks: { [framework: string]: string[] }
  user_departments: string[]

}

export const useConfigOptions = () => {
  const [config, setConfig] = useState<ConfigOptions | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    const fetchConfig = async () => {
      try {
        setLoading(true)
        const res = await fetch(`${API_BASE_URL}/frontend/config`)
        if (!res.ok) throw new Error("Failed to fetch config")
        const data = await res.json()
        if (isMounted) {
          setConfig(data)
          setError(null)
        }
      } catch (err: any) {
        if (isMounted) setError(err.message || "Unknown error")
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    fetchConfig()

    return () => {
      isMounted = false
    }
  }, [])

  return { config, loading, error }
}

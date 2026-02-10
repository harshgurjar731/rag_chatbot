import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/auth-context/AuthContext";
import { API_BASE_URL } from "@/constants";
import { useConfigOptions } from "@/hooks/useConfigOptions";
import axios from "axios";
import { useToast } from "@/hooks/use-toast";

type Mode = "login" | "signup";

export default function Login() {
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [department, setDepartment] = useState("");
  const { config, loading } = useConfigOptions();
  const { toast } = useToast();

  const { login } = useAuth();
  const navigate = useNavigate();

  const toggleMode = (mode: Mode) => {
    setMode(mode);
    setUsername("");
    setPassword("");
    setConfirmPassword("");
    setDepartment("");
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === "signup" && password !== confirmPassword) {
      alert("Passwords do not match");
      return;
    }

    try {
        if (mode === "signup") {
            await axios.post(`${API_BASE_URL}/auth/signup`, {
            username,
            password,
            confirm_password: confirmPassword,
            department,
            });
            toast({
                title: "Account Created! 🎉",
                description: `Please login to continue using the application.`,
            });
            toggleMode("login")
        } else {
            const res = await axios.post(`${API_BASE_URL}/auth/login`, {
            username,
            password,
            });

            const data = res.data;
            console.log("LoggedIn user", data.user);
            login(data.user, data.access_token);
            navigate("/");
        }
        } catch (error: any) {
            toast({
                title: "Error",
                description:
                error?.response?.data?.detail || "Something went wrong.",
                variant: "destructive",
            });
        }
  };

  return (
    <div className="min-h-screen bg-gradient-surface">
      {/* Header */}
      <div className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-gradient-primary">
              <Bot className="h-8 w-8 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                Knowledge Assistant Hub
              </h1>
              <p className="text-muted-foreground">
                Secure access to your AI assistants
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-12">
        <div className="flex justify-center">
          <Card className="w-full max-w-md bg-gradient-card border-chatbot-primary/20">
            <CardContent className="p-6">
              {/* Title */}
              <div className="mb-6 text-center">
                <h2 className="text-2xl font-semibold text-foreground">
                  {mode === "login" ? "Login to your account" : "Create an account"}
                </h2>
                <p className="text-muted-foreground text-sm mt-1">
                  {mode === "login"
                    ? "Enter your credentials to continue"
                    : "Fill in the details below to get started"}
                </p>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="username" className="text-sm font-medium">
                      Username
                    </Label>
                    <Input
                      id="username"
                      placeholder="Enter your username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="mt-1.5"
                      required
                    />
                  </div>

                  <div>
                    <Label htmlFor="password" className="text-sm font-medium">
                      Password
                    </Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="mt-1.5"
                      required
                    />
                  </div>

                  {mode === "signup" && (
                    <>
                      <div>
                        <Label
                          htmlFor="confirmPassword"
                          className="text-sm font-medium"
                        >
                          Confirm Password
                        </Label>
                        <Input
                          id="confirmPassword"
                          type="password"
                          placeholder="Re-enter password"
                          value={confirmPassword}
                          onChange={(e) =>
                            setConfirmPassword(e.target.value)
                          }
                          className="mt-1.5"
                          required
                        />
                      </div>

                      <div>
                        <Label
                          htmlFor="department"
                          className="text-sm font-medium"
                        >
                          Department
                        </Label>
                        <select
                          id="department"
                          value={department}
                          onChange={(e) => setDepartment(e.target.value)}
                          required
                          className="mt-1.5 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-chatbot-primary"
                        >
                          <option value="">Select department</option>
                          {config.user_departments?.map((dept) => (
                            <option key={dept} value={dept}>
                              {dept}
                            </option>
                          ))}
                        </select>
                      </div>
                    </>
                  )}
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-4 pt-2">
                  <Button
                    type="submit"
                    variant="chatbot"
                    size="lg"
                  >
                    {mode === "login" ? "Login" : "Create Account"}
                  </Button>

                  <div className="text-center text-sm text-muted-foreground">
                    {mode === "login" ? (
                      <>
                        Don’t have an account?{" "}
                        <button
                          type="button"
                          onClick={() => toggleMode("signup")}
                          className="font-medium text-chatbot-primary hover:underline"
                        >
                          Sign up
                        </button>
                      </>
                    ) : (
                      <>
                        Already have an account?{" "}
                        <button
                          type="button"
                          onClick={() => toggleMode("login")}
                          className="font-medium text-chatbot-primary hover:underline"
                        >
                          Login
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// src/components/SidebarLayout.tsx
import { useState } from "react"
import { Menu, X, Home, Settings, Info, Database } from "lucide-react"
import { Outlet, Link, useLocation } from "react-router-dom"

export default function SidebarLayout() {
    const [isOpen, setIsOpen] = useState(false) // mobile toggle
    const [collapsed, setCollapsed] = useState(true) // desktop collapse
    const location = useLocation()

    const navItems = [
        { to: "/", label: "Dashboard", icon: <Home size={18} /> },
        { to: "/evaluation", label: "Evaluation", icon: <Settings size={18} /> },
        { to: "/datastore", label: "Datastore", icon: <Database size={18} /> },
        { to: "/datastore2", label: "Datastore2", icon: <Database size={18} /> },
        { to: "/about", label: "About", icon: <Info size={18} /> },
    ]

    return (
        <div className="flex h-screen">
            {/* Sidebar */}
            <div
                className={`fixed md:static top-0 left-0 h-full bg-gray-900 text-white transform transition-all duration-300 flex flex-col
          ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
          ${collapsed ? "w-16" : "w-56"}
        `}
            >
                {/* Logo / Collapse Toggle */}
                <div className="flex items-center justify-between p-4">
                    {!collapsed && <span className="font-bold text-lg"></span>}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="hidden md:block text-gray-400 hover:text-white"
                    >
                        {collapsed ? <Menu size={20} /> : <X size={20} />}
                    </button>
                </div>

                {/* Navigation */}
                <nav className="flex-1 space-y-2 px-2">
                    {navItems.map(({ to, label, icon }) => {
                        const active = location.pathname === to
                        return (
                            <Link
                                key={to}
                                to={to}
                                className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors
                  ${active ? "bg-gray-800 text-blue-400" : "text-gray-300 hover:bg-gray-800 hover:text-white"}
                `}
                                title={collapsed ? label : ""}
                            >
                                {icon}
                                {!collapsed && <span>{label}</span>}
                            </Link>
                        )
                    })}
                </nav>
            </div>

            {/* Overlay for mobile */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 md:hidden"
                    onClick={() => setIsOpen(false)}
                ></div>
            )}

            {/* Main content */}
            <div className="flex-1 flex flex-col">

                {/* Routed Page Content */}
                <main className="flex-1 bg-gray-100 overflow-y-auto">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}

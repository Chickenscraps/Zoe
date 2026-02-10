import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Briefcase, 
  History, 
  Scan, 
  Map, 
  BrainCircuit, 
  Activity, 
  Settings,
  Menu,
  X
} from 'lucide-react';
import { cn } from '../lib/utils';

const NAV_ITEMS = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Positions', path: '/positions', icon: Briefcase },
  { label: 'Trades', path: '/trades', icon: History },
  { label: 'Scanner', path: '/scanner', icon: Scan },
  { label: 'Plan', path: '/plan', icon: Map },
  { label: 'Thoughts', path: '/thoughts', icon: BrainCircuit },
  { label: 'Health', path: '/health', icon: Activity },
  { label: 'Settings', path: '/settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const closeSidebar = () => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-text-primary flex">
      {/* Sidebar */}
      <aside 
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-surface border-r border-border transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
          !sidebarOpen && "-translate-x-full"
        )}
      >
        <div className="h-16 flex items-center px-6 border-b border-border">
          <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
            ZOE TERMINAL
          </h1>
        </div>
        
        <nav className="p-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={closeSidebar}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive 
                    ? "bg-surface-highlight text-white" 
                    : "text-text-secondary hover:text-white hover:bg-surface-highlight/50"
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        
        <div className="absolute bottom-4 left-4 right-4">
          <div className="bg-surface-highlight/50 p-3 rounded-md border border-border">
             <div className="text-xs text-text-secondary mb-1">Instance</div>
             <div className="text-xs font-mono text-white truncate">primary-v4-live</div>
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-border bg-background/50 backdrop-blur-sm sticky top-0 z-40 flex items-center justify-between px-6">
          <button 
            className="lg:hidden p-2 -ml-2 text-text-secondary"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X /> : <Menu />}
          </button>
          
          <div className="flex items-center gap-4 ml-auto">
            <div className="flex items-center gap-4 md:gap-6 text-sm">
               <div className="flex flex-col items-end">
                 <span className="text-[10px] md:text-xs text-text-secondary leading-tight">Equity</span>
                 <span className="font-mono font-medium text-white">$2,000.00</span>
               </div>
               <div className="h-6 w-px bg-border hidden xs:block" />
               <div className="hidden xs:block bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded text-[10px] font-medium tracking-wider">
                 PAPER
               </div>
            </div>
          </div>
        </header>

        <main className="flex-1 p-6 overflow-auto">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

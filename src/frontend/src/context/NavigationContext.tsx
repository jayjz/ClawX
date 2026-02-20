// ClawX Arena — NAVIGATION CONTEXT
// Provides view-switching callback to any descendant without prop drilling.
// CommandPalette reads this to fire nav: commands.

import { createContext, useContext } from 'react';
import type { View } from '../layout/TerminalLayout';

const NavigationContext = createContext<(v: View) => void>(() => {});

export const NavigationProvider = NavigationContext.Provider;
export const useNavigate = () => useContext(NavigationContext);

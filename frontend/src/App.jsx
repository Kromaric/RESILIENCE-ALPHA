import { AppProvider } from './context/AppContext';
import { useApp } from './context/useApp';
import PinScreen from './components/PinScreen';
import FaceAuthScreen from './components/FaceAuthScreen';
import FaceEnrollScreen from './components/FaceEnrollScreen';
import HomeScreen from './components/HomeScreen';
import SendContactScreen from './components/SendContactScreen';
import VerifyScreen from './components/VerifyScreen';
import ReceiveScreen from './components/ReceiveScreen';
import ActivityScreen from './components/ActivityScreen';
import BottomNav from './components/BottomNav';
import DemoController from './components/DemoController';

/**
 * Main application router container.
 * Enforces the exact 390x844 mobile frame with IBM Plex Sans typography.
 * No emojis used.
 */
function MobileApp() {
  const { currentScreen } = useApp();

  return (
    <div className="min-h-screen bg-[#faf9f5] flex items-center justify-center p-4 relative antialiased selection:bg-[#dcecef]">
      {/* Mobile Device Container (iPhone 14 / standard 390x844) */}
      <main
        className="w-[390px] h-[844px] bg-[#f5f6f4] text-[#0f1a1d] flex flex-col overflow-hidden rounded-2xl shadow-xl border border-[#d5dcdf] relative font-sans text-[15px] leading-[22px]"
      >
        {/* Active Screen Rendering */}
        {currentScreen === 'PIN' && <PinScreen />}
        {currentScreen === 'FACE_AUTH' && <FaceAuthScreen />}
        {currentScreen === 'FACE_ENROLL' && <FaceEnrollScreen />}
        {currentScreen === 'HOME' && <HomeScreen />}
        {currentScreen === 'SEND_CONTACT' && <SendContactScreen />}
        {currentScreen === 'VERIFY' && <VerifyScreen />}
        {currentScreen === 'RECEIVE' && <ReceiveScreen />}
        {currentScreen === 'ACTIVITY' && <ActivityScreen />}

        {/* Bottom Navigation Bar (visible on dashboard views, hidden on PIN and Face Auth/Enroll) */}
        {currentScreen !== 'PIN' && currentScreen !== 'FACE_AUTH' && currentScreen !== 'FACE_ENROLL' && <BottomNav />}
      </main>

      {/* Floating Demo Resilience Controls */}
      <DemoController />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <MobileApp />
    </AppProvider>
  );
}

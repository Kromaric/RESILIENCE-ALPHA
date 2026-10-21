import { AppProvider } from './context/AppContext';
import { useApp } from './context/useApp';
import LoginScreen from './components/LoginScreen';
import RegisterScreen from './components/RegisterScreen';
import FaceAuthScreen from './components/FaceAuthScreen';
import FaceEnrollScreen from './components/FaceEnrollScreen';
import HomeScreen from './components/HomeScreen';
import SendContactScreen from './components/SendContactScreen';
import VerifyScreen from './components/VerifyScreen';
import ReceiveScreen from './components/ReceiveScreen';
import ActivityScreen from './components/ActivityScreen';
import BottomNav from './components/BottomNav';

/**
 * Main application router container.
 * Sur téléphone : plein écran (hauteur visible réelle, zones sûres des encoches).
 * Sur ordinateur (≥ 640 px) : cadre de téléphone 390x844 centré, pour la démonstration.
 * No emojis used.
 */
function MobileApp() {
  const { currentScreen } = useApp();

  return (
    <div className="min-h-dvh bg-[#faf9f5] sm:flex sm:items-center sm:justify-center sm:p-4 relative antialiased selection:bg-[#dcecef]">
      {/* Téléphone : plein écran. Ordinateur : cadre 390x844 (iPhone 14), réduit si la fenêtre est basse */}
      <main
        className="w-full h-dvh pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] sm:pt-0 sm:pb-0 sm:w-[390px] sm:h-[844px] sm:max-h-[calc(100dvh-2rem)] bg-[#f5f6f4] text-[#0f1a1d] flex flex-col overflow-hidden sm:rounded-2xl sm:shadow-xl sm:border sm:border-[#d5dcdf] relative font-sans text-[15px] leading-[22px]"
      >
        {/* Active Screen Rendering */}
        {currentScreen === 'LOGIN' && <LoginScreen />}
        {currentScreen === 'REGISTER' && <RegisterScreen />}
        {currentScreen === 'FACE_AUTH' && <FaceAuthScreen />}
        {currentScreen === 'FACE_ENROLL' && <FaceEnrollScreen />}
        {currentScreen === 'HOME' && <HomeScreen />}
        {currentScreen === 'SEND_CONTACT' && <SendContactScreen />}
        {currentScreen === 'VERIFY' && <VerifyScreen />}
        {currentScreen === 'RECEIVE' && <ReceiveScreen />}
        {currentScreen === 'ACTIVITY' && <ActivityScreen />}

        {/* Bottom Navigation Bar (visible on dashboard views, hidden on auth/enroll screens) */}
        {currentScreen !== 'LOGIN' &&
          currentScreen !== 'REGISTER' &&
          currentScreen !== 'FACE_AUTH' &&
          currentScreen !== 'FACE_ENROLL' && <BottomNav />}
      </main>
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

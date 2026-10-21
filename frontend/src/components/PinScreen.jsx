import { useState, useEffect, useCallback } from 'react';
import { Delete, UserPlus } from 'lucide-react';
import Header from './Header';
import { useApp } from '../context/useApp';

/**
 * Screen 1: PIN login screen.
 * Displays 6-digit PIN input with custom numeric keypad.
 * No emojis used.
 */
export default function PinScreen() {
  const { handleLogin, setCurrentScreen } = useApp();
  const [pin, setPin] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  // Handle digit press
  const handleDigit = useCallback((digit) => {
    setPin((prev) => {
      if (prev.length < 6 && !isAuthenticating) {
        const nextPin = prev + digit;
        if (nextPin.length === 6) {
          setIsAuthenticating(true);
          setTimeout(() => {
            handleLogin(nextPin);
          }, 250);
        }
        return nextPin;
      }
      return prev;
    });
  }, [handleLogin, isAuthenticating]);

  // Handle backspace
  const handleDelete = useCallback(() => {
    if (!isAuthenticating) {
      setPin((prev) => prev.slice(0, -1));
    }
  }, [isAuthenticating]);

  // Physical keyboard support
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key >= '0' && e.key <= '9') {
        handleDigit(e.key);
      } else if (e.key === 'Backspace') {
        handleDelete();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleDigit, handleDelete]);

  const keypadNumbers = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['', '0', 'delete'],
  ];

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto no-scrollbar pb-6">
      {/* Top Header */}
      <Header />

      {/* Main Content */}
      <div className="flex flex-col items-center justify-center px-6 pt-4">
        {/* User Avatar */}
        <div className="w-16 h-16 rounded-full bg-[#dcecef] text-[#0a4552] flex items-center justify-center font-semibold text-xl tracking-wide shadow-xs">
          CT
        </div>

        {/* Greeting & Prompt */}
        <h2 className="text-2xl font-semibold text-[#0f1a1d] mt-4 tracking-tight">
          Bonjour Camille
        </h2>
        <p className="text-[#55636a] text-[14px] mt-1 text-center">
          Saisissez votre code orbe à 6 chiffres
        </p>

        {/* 6-dot PIN indicator */}
        <div className="flex items-center gap-3.5 my-8" aria-label={`Code saisi: ${pin.length} sur 6 chiffres`}>
          {[0, 1, 2, 3, 4, 5].map((index) => {
            const isFilled = index < pin.length;
            return (
              <div
                key={index}
                className={`w-3.5 h-3.5 rounded-full transition-all duration-150 ${
                  isFilled
                    ? 'bg-[#0e5a6b] scale-105'
                    : 'border-2 border-[#d5dcdf] bg-white'
                }`}
              />
            );
          })}
        </div>

        {/* Numeric Keypad (3x4) */}
        <div className="grid grid-cols-3 gap-x-6 gap-y-3.5 w-full max-w-[280px]">
          {keypadNumbers.flat().map((item, idx) => {
            if (item === '') {
              return <div key={`empty-${idx}`} className="w-16 h-14" />;
            }

            if (item === 'delete') {
              return (
                <button
                  key="btn-delete"
                  type="button"
                  onClick={handleDelete}
                  disabled={isAuthenticating || pin.length === 0}
                  className="w-16 h-14 mx-auto rounded-2xl flex items-center justify-center text-[#55636a] hover:text-[#0f1a1d] active:bg-[#e4ebed] transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-default"
                  aria-label="Effacer le dernier chiffre"
                >
                  <Delete className="w-6 h-6 stroke-[1.75]" />
                </button>
              );
            }

            return (
              <button
                key={`btn-${item}`}
                type="button"
                onClick={() => handleDigit(item)}
                disabled={isAuthenticating || pin.length >= 6}
                className="w-16 h-14 mx-auto rounded-2xl flex items-center justify-center text-[22px] font-semibold text-[#0f1a1d] bg-white border border-[#d5dcdf] shadow-xs active:bg-[#dcecef] active:border-[#0e5a6b] transition-all cursor-pointer hover:border-[#7f8c93]"
              >
                {item}
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer Info & Links */}
      <div className="px-6 text-center mt-6 flex flex-col gap-2">
        <div className="flex items-center justify-center gap-4 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              setPin('');
              handleLogin('000000');
            }}
            className="text-[#0e5a6b] hover:underline cursor-pointer"
          >
            Code oublié ?
          </button>
          <span className="text-[#d5dcdf]">|</span>
          <button
            type="button"
            onClick={() => setCurrentScreen('REGISTER')}
            className="text-[#0e5a6b] hover:underline cursor-pointer inline-flex items-center gap-1"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Créer un compte</span>
          </button>
        </div>
        <p className="text-[12px] text-[#55636a] leading-tight">
          3 essais. Ensuite, le compte est bloqué 10 min.
        </p>
      </div>
    </div>
  );
}

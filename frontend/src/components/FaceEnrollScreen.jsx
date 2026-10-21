import { useState, useEffect, useRef, useCallback } from 'react';
import { ArrowLeft, ScanFace, CheckCircle2, AlertCircle, ShieldCheck, RefreshCw, CameraOff, Loader2 } from 'lucide-react';
import { useApp } from '../context/useApp';
import { enrollFace } from '../services/api';

/**
 * Screen: Biometric Facial Enrollment (RGPD Art. 9).
 * Allows the user to register their face with explicit consent.
 * Strictly requires an active camera stream with live frames.
 * No emojis used.
 */
export default function FaceEnrollScreen() {
  const { authToken, setAuthToken, setCurrentScreen, syncBackendData, setUser } = useApp();

  const [consentChecked, setConsentChecked] = useState(false);
  const [enrollState, setEnrollState] = useState('IDLE'); // 'IDLE', 'CAPTURING', 'ENROLLED', 'ERROR'
  const [capturedCount, setCapturedCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');

  // Camera state: 'CHECKING' | 'ACTIVE' | 'ERROR'
  const [cameraStatus, setCameraStatus] = useState('CHECKING');
  const [cameraError, setCameraError] = useState('');
  const [cameraRetry, setCameraRetry] = useState(0);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const isEnrollingRef = useRef(false);
  const isMountedRef = useRef(true);

  const totalFrames = 16;
  const intervalMs = 250;

  // Single frame capture as base64 JPEG without prefix
  const captureCurrentFrameB64 = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return null;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video.videoWidth === 0 || video.videoHeight === 0) return null;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    const commaIndex = dataUrl.indexOf(',');
    return commaIndex !== -1 ? dataUrl.slice(commaIndex + 1) : dataUrl;
  }, []);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const retryCamera = () => {
    setCameraStatus('CHECKING');
    setCameraError('');
    setCameraRetry((c) => c + 1);
  };

  useEffect(() => {
    isMountedRef.current = true;
    let streamInstance = null;

    async function startCamera() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (!isMountedRef.current) return;
        setCameraStatus('ERROR');
        setCameraError("Votre navigateur ne supporte pas l'accès à la caméra.");
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 640 },
          },
        });

        if (!isMountedRef.current) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamInstance = stream;
        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.onloadedmetadata = () => {
            videoRef.current?.play().then(() => {
              const track = stream.getVideoTracks()[0];
              if (track && track.readyState === 'live' && videoRef.current.videoWidth > 0) {
                setCameraStatus('ACTIVE');
              } else {
                setCameraStatus('ERROR');
                setCameraError('Le flux vidéo de la caméra est indisponible.');
              }
            }).catch((playErr) => {
              setCameraStatus('ERROR');
              setCameraError('Impossible de démarrer la vidéo : ' + playErr.message);
            });
          };
        }
      } catch (err) {
        console.warn('Webcam initialization failed in FaceEnroll:', err);
        if (!isMountedRef.current) return;
        setCameraStatus('ERROR');
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setCameraError("Accès à la caméra refusé. Veuillez autoriser l'accès dans les paramètres de votre navigateur.");
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          setCameraError('Aucune caméra détectée sur votre appareil.');
        } else {
          setCameraError("Erreur d'accès à la caméra : " + (err.message || 'Périphérique indisponible.'));
        }
      }
    }

    startCamera();

    return () => {
      isMountedRef.current = false;
      if (streamInstance) {
        streamInstance.getTracks().forEach((track) => track.stop());
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, [cameraRetry]);

  const handleStartEnrollment = useCallback(async () => {
    if (cameraStatus !== 'ACTIVE') {
      setEnrollState('ERROR');
      setErrorMessage('La caméra doit être active pour enregistrer votre visage.');
      return;
    }

    if (!consentChecked) {
      setEnrollState('ERROR');
      setErrorMessage('Veuillez accepter le consentement biométrique pour continuer.');
      return;
    }

    if (isEnrollingRef.current) return;
    isEnrollingRef.current = true;
    setEnrollState('CAPTURING');
    setErrorMessage('');
    setCapturedCount(0);

    try {
      const frames = [];

      for (let i = 0; i < totalFrames; i++) {
        const frameB64 = captureCurrentFrameB64();
        if (frameB64) {
          frames.push(frameB64);
        }
        setCapturedCount(i + 1);
        if (i < totalFrames - 1) {
          await sleep(intervalMs);
        }
      }

      if (frames.length < 6) {
        throw new Error('Capture insuffisante : assurez-vous que votre caméra diffuse une image nette.');
      }

      // Call backend enrollment endpoint with real camera frames
      let latestToken = authToken;
      if (authToken) {
        const enrollRes = await enrollFace(frames, authToken);
        if (enrollRes?.token?.access_token && setAuthToken) {
          latestToken = enrollRes.token.access_token;
          setAuthToken(latestToken);
        }
      } else {
        throw new Error('Session non authentifiée. Veuillez vous reconnecter.');
      }

      setEnrollState('ENROLLED');
      if (setUser) {
        setUser((prev) => ({ ...prev, faceEnrolled: true }));
      }
      await sleep(1000);

      if (latestToken) {
        await syncBackendData(latestToken);
      }
      setCurrentScreen('HOME');
    } catch (err) {
      setEnrollState('ERROR');
      setErrorMessage(err.message || "Échec de l'enregistrement. Vérifiez votre éclairage et réessayez.");
    } finally {
      isEnrollingRef.current = false;
    }
  }, [cameraStatus, consentChecked, captureCurrentFrameB64, authToken, setAuthToken, setUser, syncBackendData, setCurrentScreen]);

  const handleSkip = () => {
    setCurrentScreen('HOME');
  };

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto no-scrollbar pb-5 select-none">
      {/* Top Header */}
      <div>
        <div className="px-5 pt-4 pb-2 flex items-center justify-between">
          <button
            type="button"
            onClick={handleSkip}
            className="p-1 -ml-1 text-[#0f1a1d] hover:text-[#0e5a6b] rounded-lg transition-colors cursor-pointer"
            aria-label="Passer"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>

          <span className="bg-[#dcecef] text-[#0a4552] rounded-full px-2.5 py-0.5 text-xs font-semibold inline-flex items-center gap-1 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Enrôlement biométrique</span>
          </span>
        </div>

        {/* Title & Instructions */}
        <div className="px-6 pt-2 text-center flex flex-col items-center">
          <h2 className="text-[20px] font-semibold text-[#0f1a1d] tracking-tight">
            Activer la reconnaissance faciale
          </h2>
          <p className="text-xs text-[#55636a] mt-1 max-w-[290px] leading-relaxed">
            Regardez la caméra et tournez lentement la tête de gauche à droite pour enregistrer votre profil sécurisé.
          </p>
        </div>

        {/* Video Viewport */}
        <div className="mt-4 px-6 flex flex-col items-center">
          <div className="relative w-64 h-64 rounded-full overflow-hidden border-4 border-[#0e5a6b] shadow-md bg-black flex items-center justify-center">
            {/* Live Camera Video */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover transform -scale-x-100 ${
                cameraStatus === 'ACTIVE' ? 'opacity-100' : 'opacity-0'
              }`}
            />

            {/* Hidden canvas for capturing frame snapshots */}
            <canvas ref={canvasRef} className="hidden" />

            {/* Camera loading state */}
            {cameraStatus === 'CHECKING' && (
              <div className="absolute inset-0 bg-[#0f1a1d] flex flex-col items-center justify-center p-4 text-center">
                <Loader2 className="w-8 h-8 text-[#0e5a6b] animate-spin mb-2" />
                <span className="text-xs text-white font-medium">Activation de la caméra...</span>
              </div>
            )}

            {/* Camera error fallback */}
            {cameraStatus === 'ERROR' && (
              <div className="absolute inset-0 bg-[#1c2427] flex flex-col items-center justify-center p-4 text-center">
                <CameraOff className="w-10 h-10 text-[#f47066] mb-2" />
                <span className="text-xs text-white font-medium mb-1">Caméra indisponible</span>
                <p className="text-[11px] text-[#9aa5aa] leading-tight mb-3 px-2">
                  {cameraError || "Vérifiez les permissions de votre navigateur."}
                </p>
                <button
                  type="button"
                  onClick={retryCamera}
                  className="px-3 py-1.5 rounded-lg bg-[#0e5a6b] hover:bg-[#0a4552] text-white text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Réessayer</span>
                </button>
              </div>
            )}

            {/* Scanning Overlay Animation */}
            {enrollState === 'CAPTURING' && cameraStatus === 'ACTIVE' && (
              <div className="absolute inset-0 bg-[#0e5a6b]/20 flex flex-col items-center justify-center">
                <div className="w-full h-1 bg-[#22c55e] absolute top-0 animate-pulse shadow-[0_0_12px_#22c55e]" />
                <div className="bg-black/75 px-3 py-1.5 rounded-full text-white text-xs font-mono font-medium backdrop-blur-xs">
                  Enregistrement {capturedCount}/{totalFrames}
                </div>
              </div>
            )}

            {/* Success Overlay */}
            {enrollState === 'ENROLLED' && (
              <div className="absolute inset-0 bg-[#13532a]/85 backdrop-blur-xs flex flex-col items-center justify-center text-white animate-fadeIn">
                <CheckCircle2 className="w-14 h-14 mb-1 text-white stroke-[2]" />
                <span className="text-sm font-semibold tracking-tight">Profil biométrique activé</span>
                <span className="text-xs opacity-90 font-mono mt-0.5">
                  100% sécurisé (RGPD Art. 9)
                </span>
              </div>
            )}

            {/* Error Overlay */}
            {enrollState === 'ERROR' && cameraStatus === 'ACTIVE' && (
              <div className="absolute inset-0 bg-[#3d1714]/85 backdrop-blur-xs flex flex-col items-center justify-center text-[#f47066] p-4 text-center animate-fadeIn">
                <AlertCircle className="w-12 h-12 mb-1.5 stroke-[2]" />
                <span className="text-xs font-semibold text-white leading-tight">
                  Échec d&apos;enregistrement
                </span>
              </div>
            )}
          </div>

          {/* Feedback error notice below viewport */}
          {enrollState === 'ERROR' && errorMessage && (
            <div className="mt-2.5 mx-2 p-2.5 rounded-xl bg-[#fde8e8] border border-[#f8b4b4] text-[#c81e1e] text-xs flex items-center gap-2 shadow-2xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span className="leading-tight">{errorMessage}</span>
            </div>
          )}

          {/* Explicit GDPR Consent Checkbox */}
          <div className="mt-4 px-2">
            <label className="flex items-start gap-2.5 cursor-pointer text-left">
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(e) => setConsentChecked(e.target.checked)}
                className="mt-0.5 w-4 h-4 text-[#0e5a6b] rounded border-[#d5dcdf] focus:ring-[#0e5a6b]"
              />
              <span className="text-[11px] text-[#55636a] leading-tight">
                J&apos;accepte le traitement de mes données biométriques (embeddings chiffrés, aucune photo stockée) conformément à l&apos;article 9 du RGPD.
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="px-5 pt-4 pb-1 flex flex-col gap-2">
        {enrollState === 'IDLE' && (
          <button
            type="button"
            disabled={!consentChecked || cameraStatus !== 'ACTIVE'}
            onClick={handleStartEnrollment}
            className="w-full h-11 bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ScanFace className="w-4 h-4" />
            <span>Commencer l&apos;enregistrement</span>
          </button>
        )}

        {enrollState === 'CAPTURING' && (
          <button
            type="button"
            disabled
            className="w-full h-11 bg-[#55636a] text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-2 shadow-xs cursor-wait"
          >
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Analyse InsightFace en cours...</span>
          </button>
        )}

        {enrollState === 'ENROLLED' && (
          <button
            type="button"
            disabled
            className="w-full h-11 bg-[#1e7a45] text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-2 shadow-xs"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Enregistrement terminé</span>
          </button>
        )}

        {enrollState === 'ERROR' && (
          <button
            type="button"
            onClick={() => {
              setEnrollState('IDLE');
              setErrorMessage('');
            }}
            className="w-full h-11 bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-xs"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Réessayer</span>
          </button>
        )}

        <button
          type="button"
          onClick={handleSkip}
          className="w-full h-10 text-xs font-semibold text-[#55636a] hover:text-[#0f1a1d] transition-colors cursor-pointer"
        >
          Passer cette étape
        </button>
      </div>
    </div>
  );
}

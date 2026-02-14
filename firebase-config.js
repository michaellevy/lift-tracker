// Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDXJF5T2i7eQ_mW8VSY92CMEJsE34znS_I",
  authDomain: "lifts-tracker-2a4ce.firebaseapp.com",
  projectId: "lifts-tracker-2a4ce",
  storageBucket: "lifts-tracker-2a4ce.firebasestorage.app",
  messagingSenderId: "733370322654",
  appId: "1:733370322654:web:87e6ec9378c828eb9cbc4f",
  measurementId: "G-SCJS0EE5SS"
};

// Initialize Firebase (using compat SDK loaded via script tags)
firebase.initializeApp(firebaseConfig);

// Enable Firestore offline persistence
firebase.firestore().enablePersistence({ synchronizeTabs: true })
  .catch((err) => {
    if (err.code === 'failed-precondition') {
      console.warn('Firestore persistence failed: multiple tabs open');
    } else if (err.code === 'unimplemented') {
      console.warn('Firestore persistence not available in this browser');
    }
  });

const db = firebase.firestore();
const auth = firebase.auth();

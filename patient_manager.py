"""
Patient Manager - Handles dynamic patient ID for all API operations
"""
import os
from dotenv import load_dotenv
load_dotenv()

class PatientManager:
    """Singleton class to manage current patient ID"""
    _instance = None
    _current_patient_id = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_patient_id = os.getenv("DEFAULT_PATIENT_ID", "p0001")
        return cls._instance
    
    def get_patient_id(self) -> str:
        """Get current patient ID"""
        return self._current_patient_id
    
    def set_patient_id(self, patient_id: str):
        """Set current patient ID"""
        self._current_patient_id = patient_id
        print(f"✅ Patient ID set to: {patient_id}")
    
    def get_base_url(self) -> str:
        """Get base URL from environment"""
        return os.getenv("CANVAS_URL", "https://iso-clinic-v3.vercel.app")

# Global singleton instance
patient_manager = PatientManager()

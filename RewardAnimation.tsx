import { motion } from 'framer-motion';
import { Crown } from 'lucide-react';

/** "+1 Tiara" rising briefly after a correct answer. */
export function RewardAnimation() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.8 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 260, damping: 16 }}
      className="inline-flex items-center gap-2 rounded-full bg-gold px-4 py-2 text-sm font-bold text-ink shadow-[0_8px_20px_-8px_rgba(154,111,12,0.8)]"
    >
      <motion.span animate={{ rotate: [0, -14, 14, 0] }} transition={{ duration: 0.7, delay: 0.2 }}>
        <Crown size={18} strokeWidth={2.4} />
      </motion.span>
      +1 Tiara
    </motion.div>
  );
}

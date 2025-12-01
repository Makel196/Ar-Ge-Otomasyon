// Common animation variants used across the application

export const logoAnimationVariants = {
    animate: {
        y: [0, -5, 0],
        scale: [1, 1.05, 1],
        filter: ["drop-shadow(0 0 0px rgba(0,0,0,0))", "drop-shadow(0 5px 5px rgba(0,0,0,0.2))", "drop-shadow(0 0 0px rgba(0,0,0,0))"],
        transition: {
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut"
        }
    },
    hover: {
        scale: 1.1,
        rotate: [0, -5, 5, 0],
        transition: {
            duration: 0.5
        }
    }
};

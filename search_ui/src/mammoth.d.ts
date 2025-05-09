declare module 'mammoth/mammoth.browser' {
    interface MammothResult {
        value: string; // The HTML string
        messages: Array<{ type: string; message: string }>;
    }

    interface MammothOptions {
        arrayBuffer?: ArrayBuffer;
        // Add other options if you use them
    }

    const mammoth: {
        convertToHtml: (options: MammothOptions) => Promise<MammothResult>;
        // Add other mammoth functions if you use them
    };
    export = mammoth; // Use 'export =' for compatibility with CJS-style module
} 
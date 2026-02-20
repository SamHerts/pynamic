#include <Python.h>
#include <stdlib.h>
#include <mpi.h>
#include <wchar.h>

#if !defined(STR)
#define XSTR(X) #X
#define STR(X) XSTR(X)
#endif

#if !defined(ROOT_DIR)
#error ROOT_DIR not defined
#endif

int main(int argc, char *argv[])
{
   char *orig_pythonpath, *pythonpath;
   unsigned long len;
   int rank, i;
   wchar_t **wargv;

   orig_pythonpath = getenv("PYTHONPATH");
   if (!orig_pythonpath) {
      pythonpath = STR(ROOT_DIR);
   }
   else {
      len = strlen(orig_pythonpath) + strlen(STR(ROOT_DIR)) + 3;
      pythonpath = (char *) malloc(strlen(orig_pythonpath) + strlen(STR(ROOT_DIR)) + 3);
      snprintf(pythonpath, len, "%s:%s", orig_pythonpath, STR(ROOT_DIR));
   }
   setenv("PYTHONPATH", pythonpath, 1);
   
   MPI_Init(&argc, &argv);

   MPI_Comm_rank(MPI_COMM_WORLD, &rank);
   printf("rank - %d\n", (int) rank);
   Py_Initialize();
   wargv = (wchar_t **) malloc(argc * sizeof(wchar_t *));
   for (i = 0; i < argc; i++)
      wargv[i] = Py_DecodeLocale(argv[i], NULL);
   PySys_SetArgvEx(argc, wargv, 0);
   for (i = 0; i < argc; i++)
      PyMem_RawFree(wargv[i]);
   free(wargv);
   PyRun_SimpleString("import pynamic_driver_mpi4py\n");
   Py_Finalize();

   MPI_Finalize();
   return 0;
}

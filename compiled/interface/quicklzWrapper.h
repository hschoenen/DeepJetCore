/*
 * quicklzWrapper.h
 *
 *  Created on: 5 Nov 2019
 *      Author: jkiesele
 */

#ifndef DEEPJETCORE_COMPILED_INTERFACE_QUICKLZWRAPPER_H_
#define DEEPJETCORE_COMPILED_INTERFACE_QUICKLZWRAPPER_H_

#include "quicklz.h"
#include <stdio.h>
#include <vector>
#include <stdint.h>
#include <string>
#include <stdexcept>

#include "version.h"

#define QUICKLZ_MAXCHUNK (0xffffffff - 400)

namespace djc{
template <class T>
class quicklz{
public:

    quicklz();
    ~quicklz();

    void reset();

    //reads header, saves total uncompressed size
    void readHeader(FILE *& ifile);

    //get uncompressed size to allocate memory if needed
    //not in bytes but in terms of T
    size_t getSize()const{return totalbytes_/sizeof(T);}

    //writes from compressed file to memory
    //returns in terms of T how many elements have been read
    size_t readCompressedBlock(FILE *& ifile, T * arr);

    //assumes you know the size that is supposed to be read
    //and memory has been allocated already!
    //returns in terms of T how many compressed elements have been read (without header)
    size_t readAll(FILE *& ifile, T * arr);

    //writes header and compressed data
    //give size in terms of T
    void writeCompressed(T * arr, size_t size, FILE *& ofile);


private:
    std::vector<size_t> chunksizes_;
    uint8_t nchunks_;
    size_t totalbytes_;
    qlz_state_decompress *state_decompress_;
    qlz_state_compress *state_compress_;
};

template <class T>
quicklz<T>::quicklz(){
    nchunks_=0;
    totalbytes_=0;
    state_decompress_ = new qlz_state_decompress();
    state_compress_ = new qlz_state_compress();
}


template <class T>
quicklz<T>::~quicklz(){
    delete state_decompress_;
    delete state_compress_ ;
}

template <class T>
void quicklz<T>::reset(){
    chunksizes_.clear();
    nchunks_ = 0;
    totalbytes_ = 0;
    delete state_decompress_;
    delete state_compress_;
    state_decompress_ = new qlz_state_decompress();
    state_compress_ = new qlz_state_compress();
}

template <class T>
void quicklz<T>::readHeader(FILE *& ifile) {
    nchunks_ = 0;
    chunksizes_.clear();
    totalbytes_ = 0;
    float version = 0;
    fread(&version, 1, sizeof(float), ifile);
    if(version != DJCDATAVERSION)
        throw std::runtime_error("quicklz<T>::readHeader: incompatible version");
    fread(&nchunks_, 1, 1, ifile);
    chunksizes_ = std::vector<size_t>(nchunks_, 0);
    size_t vecbytesize = nchunks_ * sizeof(size_t);
    fread(&chunksizes_[0], 1, vecbytesize, ifile);
    fread(&totalbytes_, 1, sizeof(size_t), ifile);
}




template <class T>
size_t quicklz<T>::readCompressedBlock(FILE *& ifile, T * arr){

    size_t chunk = 0;
    size_t readbytes = 0;
    size_t writepos = 0;
    size_t allread = 0;
    char* src = 0;

    while (chunk < nchunks_ && totalbytes_) {
        src = new char[chunksizes_.at(chunk)];
        fread(src, 1, chunksizes_.at(chunk), ifile);
        readbytes += qlz_size_decompressed(src);

        allread += qlz_decompress(src, arr, state_decompress_);
        writepos = readbytes;
        chunk++;
        arr += writepos / sizeof(T);
        delete src;
    }
    if (allread != totalbytes_) {
        std::string moreinfo = "\nexpected: ";
        moreinfo += std::to_string(totalbytes_);
        moreinfo += " got: ";
        moreinfo += std::to_string(allread);
        delete state_decompress_;
        state_decompress_ = 0;
        throw std::runtime_error(
                "quicklz::readCompressedBlock: expected size and uncompressed size don't match");
    }
    return allread / sizeof(T);
}



template<class T>
size_t quicklz<T>::readAll(FILE *& ifile, T * arr) {
    readHeader(ifile);
    return readCompressedBlock(ifile, arr);
}

template<class T>
void quicklz<T>::writeCompressed(T * arr, size_t size, FILE *& ofile) {

    size_t length = size * sizeof(T);
    char *src = (char*) (void*) arr;

    //destination buffer
    char *dst = new char[length + 400];
    size_t remaininglength = length;
    size_t len2 = 0;
    size_t startbyte = 0;
    uint8_t nchunks = 1;
    std::vector<size_t> chunksizes;

    while (remaininglength) {

        size_t uselength = 0;
        if (remaininglength > QUICKLZ_MAXCHUNK) {
            uselength = QUICKLZ_MAXCHUNK;
            remaininglength -= QUICKLZ_MAXCHUNK;
            nchunks++;
            if (!nchunks) {
                throw std::runtime_error(
                        "quicklz::writeCompressed: array size too big (O(TB))!");
            }

        } else {
            uselength = remaininglength;
            remaininglength = 0;
        }
        size_t thissize = qlz_compress(&src[startbyte], &dst[len2], uselength,
                state_compress_);
        chunksizes.push_back(thissize);
        len2 += thissize;
        startbyte += uselength;
    }
    float version = DJCDATAVERSION;
    fwrite(&version,1,sizeof(float),ofile);
    fwrite(&nchunks,1,1,ofile);
    fwrite(&chunksizes[0],1,chunksizes.size()*sizeof(size_t),ofile);
    fwrite(&length, 1, sizeof(size_t), ofile);
    fwrite(dst, len2, 1, ofile);

    //end
    delete dst;
}

}//namespace

#endif

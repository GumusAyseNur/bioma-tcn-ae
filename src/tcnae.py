
import numpy
from tcn import TCN
import time
import tensorflow
from tensorflow.keras.layers import Dense, Activation, Dropout
from tensorflow.keras.layers import Input
from tensorflow.keras.layers import Conv1D
from tensorflow.keras.layers import UpSampling1D
from tensorflow.keras.layers import AveragePooling1D
from tensorflow.keras.layers import MaxPooling1D
from tensorflow.keras import optimizers
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.models import Model
import pandas

class TCNAE:
    """
    A class used to represent the Temporal Convolutional Autoencoder (TCN-AE).

    ...

    Attributes
    ----------
    model : xxtypexx
        The TCN-AE model.

    Methods
    -------
    build_model(verbose = 1)
        Builds the model
    """
    
    model = None
    
    def __init__(self,
                 ts_dimension = 1,
                 dilations = (1, 2, 4, 8, 16),
                 nb_filters = 20,
                 kernel_size = 20,
                 nb_stacks = 1,
                 padding = 'same',
                 dropout_rate = 0.00,
                 filters_conv1d = 8,
                 activation_conv1d = 'linear',
                 latent_sample_rate = 42,
                 pooler = AveragePooling1D,
                 learning_rate = 0.001,
                 conv_kernel_init = 'glorot_normal',
                 loss = 'mean_squared_error',
                 use_early_stopping = False,
                 
                 verbose = 1
                ):
        """
        Parameters
        ----------
        ts_dimension : int
            The dimension of the time series (default is 1)
        dilations : tuple
            The dilation rates used in the TCN-AE model (default is (1, 2, 4, 8, 16))
        nb_filters : int
            The number of filters used in the dilated convolutional layers. All dilated conv. layers use the same number of filters (default is 20)
        """
        
        self.ts_dimension = ts_dimension
        self.dilations = dilations
        self.nb_filters = nb_filters
        self.kernel_size = kernel_size
        self.nb_stacks = nb_stacks
        self.padding = padding
        self.dropout_rate = dropout_rate
        self.filters_conv1d = filters_conv1d
        self.activation_conv1d = activation_conv1d
        self.latent_sample_rate = latent_sample_rate
        self.pooler = pooler
        self.learning_rate = learning_rate
        self.conv_kernel_init = conv_kernel_init
        self.loss = loss,
        self.use_early_stopping = use_early_stopping
        
        
        # build the model
        self.build_model(verbose = verbose)
        
    
    def build_model(self, verbose = 1):
        """Builds the TCN-AE model.

        If the argument `verbose` isn't passed in, the default verbosity level is used.

        Parameters
        ----------
        verbose : str, optional
            The verbosity level (default is 1)
            
        Returns
        -------
        KerasXYZType
        Todo

        Raises
        ------
        NotImplementedError
            If ...
        """
        
        tensorflow.keras.backend.clear_session()
        sampling_factor = self.latent_sample_rate
        i = Input(batch_shape=(None, 128, 1))

        # Put signal through TCN. Output-shape: (batch,sequence length, nb_filters)
        tcn_enc = TCN(nb_filters=self.nb_filters, kernel_size=self.kernel_size, nb_stacks=self.nb_stacks, dilations=self.dilations, 
                      padding=self.padding, use_skip_connections=True, dropout_rate=self.dropout_rate, return_sequences=True,
                      kernel_initializer=self.conv_kernel_init, name='tcn-enc')(i)

        # Now, adjust the number of channels...
        enc_flat = Conv1D(filters=self.filters_conv1d, kernel_size=1, activation=self.activation_conv1d, padding=self.padding)(tcn_enc)

        ## Do some average (max) pooling to get a compressed representation of the time series (e.g. a sequence of length 8)
        enc_pooled = self.pooler(pool_size=sampling_factor, strides=None, padding='valid', data_format='channels_last')(enc_flat)
        
        # If you want, maybe put the pooled values through a non-linear Activation
        enc_out = Activation("linear")(enc_pooled)

        # Now we should have a short sequence, which we will upsample again and then try to reconstruct the original series
        dec_upsample = UpSampling1D(size=sampling_factor)(enc_out)

        dec_reconstructed = TCN(nb_filters=self.nb_filters, kernel_size=self.kernel_size, nb_stacks=self.nb_stacks, dilations=self.dilations, 
                                padding=self.padding, use_skip_connections=True, dropout_rate=self.dropout_rate, return_sequences=True,
                                kernel_initializer=self.conv_kernel_init, name='tcn-dec')(dec_upsample)

        # Put the filter-outputs through a dense layer finally, to get the reconstructed signal
        o = Dense(self.ts_dimension, activation='linear')(dec_reconstructed)

        model = Model(inputs=[i], outputs=[o])

        adam = optimizers.Adam(learning_rate=self.learning_rate, beta_1=0.9, beta_2=0.999, epsilon=1e-08, amsgrad=True)
        model.compile(loss=self.loss, optimizer=adam, metrics=[self.loss])
        if verbose > 1:
            model.summary()
        self.model = model
    
    def fit(self,  X_train, X_valid, batch_size=32, epochs=40, verbose = 1):
        my_callbacks = None
        if self.use_early_stopping:
            my_callbacks = [EarlyStopping(monitor='val_loss', patience=2, min_delta=1e-4, restore_best_weights=True)]

        keras_verbose = 0
        if verbose > 0:
            print("> Starting the Training...")
            keras_verbose = 2
        start = time.time()
        history = self.model.fit(X_train,X_train,
                            batch_size=batch_size, 
                            epochs=epochs, 
                            validation_data=(X_valid,X_valid ),
                            
                            shuffle=True,
                            callbacks=my_callbacks,
                            verbose=keras_verbose)
        if verbose > 0:
            print("> Training Time :", round(time.time() - start), "seconds.")
            
    def predict_validation(self, validation_X):
        X_rec = self.model.predict(validation_X)
    
        # do some padding in the end, since not necessarily the whole time series is reconstructed
        X_rec = numpy.pad(X_rec, ((0, 0), (0, validation_X.shape[1] - X_rec.shape[1]), (0, 0)), 'constant')
        E_rec = (X_rec - validation_X).squeeze()
        mse = numpy.mean(numpy.square(E_rec), axis=-1)
        return mse

    def predict(self, test_X):
        X_rec = self.model.predict(test_X)

        # do some padding in the end, since not necessarily the whole time series is reconstructed
        X_rec = numpy.pad(X_rec, ((0, 0), (0, test_X.shape[1] - X_rec.shape[1]), (0, 0)), 'constant')
        E_rec = (X_rec - test_X).squeeze()
        mse = numpy.mean(numpy.square(E_rec), axis=-1)
        return mse  
   
